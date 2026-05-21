from __future__ import annotations

import asyncio
from enum import Enum
import inspect
import platform
import re
import time

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.logging import get_logger
from typing import Any, AsyncIterator, Awaitable, Callable
from db.repositories.api_key import APIKeyRepository
from llm.client import LLMClient
from llm.errors import RateLimitError, LLMUnavailableError, LLMError
from llm.router import FreeTierRouter
from core.tool_groups import get_enabled_tool_names, get_enabled_tool_schemas
from core.registry import ToolRegistry
from core.types import (
    StreamEvent,
)
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager
from services.api_key_manager import APIKeyManager
from services.settings_service import SettingsService
from db.database import async_session

logger = get_logger(__name__)

# Regex patterns that identify sudo/su commands.
_SUDO_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bsudo\b"),
    re.compile(r"\bsu\s+-"),
]


def _is_sudo_command(command: str) -> bool:
    """Check if a command string requires sudo/su privileges."""
    return any(pat.search(command) for pat in _SUDO_PATTERNS)


# Type alias for the TUI password-provider callback.
# Returns the password string, or None if the user cancelled.
SudoPasswordProvider = Callable[[], Awaitable[str | None]]


class Channel(str, Enum):
    TELEGRAM = "telegram"
    WEB = "web"
    TUI = "tui"


class Agent:
    def __init__(
        self,
        registry: ToolRegistry,
        llm: LLMClient,
        config_manager: ConfigManager,
        fernet: Fernet,
        router: FreeTierRouter | None = None,
    ) -> None:
        self._registry = registry
        self._llm = llm
        self._router = router
        self._current_key_id: str | None = getattr(llm, "current_key_id", None)
        self.model_name = llm.config.default_model
        self._config_manager = config_manager
        self._fernet = fernet

    # ------------------------------------------------------------------
    # Public unified entry point — all interface adapters call this.
    # ------------------------------------------------------------------

    async def chat(
        self,
        message: str,
        session_id: str,
        channel: Channel,
        model: str | None = None,
        tool_groups: dict[str, bool] | None = None,
        sudo_password_provider: SudoPasswordProvider | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Unified streaming entry point for web, telegram, and TUI adapters."""
        db = async_session()
        session_closed = False

        async def _close_db() -> None:
            nonlocal session_closed
            if not session_closed:
                session_closed = True
                try:
                    await db.close()
                except Exception:
                    pass

        try:
            async for event in self.run_stream(
                message,
                session_id,
                db,
                channel=channel,
                model=model,
                tool_groups=tool_groups,
                sudo_password_provider=sudo_password_provider,
            ):
                if event.type in ("done", "error"):
                    await _close_db()
                yield event
        finally:
            if not session_closed:
                await _close_db()

    async def run_stream(
        self,
        user_request: str,
        session_id: str,
        db: AsyncSession,
        channel: Channel,
        model: str | None = None,
        tool_groups: dict[str, bool] | None = None,
        sudo_password_provider: SudoPasswordProvider | None = None,
    ) -> AsyncIterator[StreamEvent]:
        memory_manager = MemoryManager(db)

        # Read safety_mode once per request.
        settings_service = SettingsService(db)
        app_settings = await settings_service.get_settings()
        safety_mode: bool = app_settings.safety_mode
        tool_schemas = get_enabled_tool_schemas(self._registry, tool_groups)
        enabled_tool_names = get_enabled_tool_names(tool_groups)

        system = build_system_prompt(
            self._config_manager,
            tool_schemas=tool_schemas,
            safety_mode=safety_mode,
            channel=channel.value,
        )
        logger.info("\n\nsystem prompt: \n%s", system)

        history = await memory_manager.get_history_as_openai_messages(session_id)
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.extend(history)
        messages.append({"role": "user", "content": user_request})

        model_name: str | None = None
        selected_provider: str | None = None
        preferred_model_ref: str | None = None
        if model:
            selected_provider, model_name = model.split("/", maxsplit=1)
            preferred_model_ref = model

        api_key_manager = APIKeyManager(repo=APIKeyRepository(db), fernet=self._fernet)

        answer_parts: list[str] = []
        last_done_event: StreamEvent | None = None
        max_retries = 20
        retry_exhausted_error: str | None = None
        active_model = model_name or self._llm.config.default_model
        selected_provider_bound = bool(
            selected_provider and self._llm.config.name == selected_provider
        )
        transient_cooldown_seconds = 300

        async def _pick_next_config(provider: str, model: str):
            from llm.providers import build_provider_config

            repo = api_key_manager.repo
            available = await repo.pick_available_key(provider=provider, model=model)
            if available is None:
                available = await repo.pick_available_key(provider=None, model=None)
            if available is None:
                api_key_manager.last_rotated_key_id = None
                return None

            api_key_manager.last_rotated_key_id = available.id
            raw_key = api_key_manager.fernet.decrypt(available.encrypted_key.encode()).decode()
            return build_provider_config(available.provider, api_key=raw_key)

        # ── Gated tool executor ──────────────────────────────────────────────────
        # Handles dangerous/sudo commands inline:
        #   - Web/Telegram: blocked entirely (no confirmation flow).
        #   - TUI: sudo password collected via sudo_password_provider and executed
        #          immediately; non-sudo dangerous commands execute with confirmed=True.
        #   - Safety mode ON: all dangerous commands blocked regardless of channel.

        async def _gated_tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
            if name not in enabled_tool_names:
                return {
                    "status": "disabled",
                    "message": f"Tool '{name}' is disabled for this chat session.",
                }

            result = await self._execute_tool(name, args)

            if result.get("status") == "needs_confirmation":
                cmd_str = args.get("command", "")
                is_sudo = _is_sudo_command(cmd_str)

                # ── Web & Telegram: block all dangerous commands ─────────────
                if channel in (Channel.WEB, Channel.TELEGRAM):
                    channel_name = "web" if channel == Channel.WEB else "Telegram"
                    logger.info(
                        "Dangerous command blocked on %s: tool=%s session=%s",
                        channel_name, name, session_id,
                    )
                    return {
                        "status": "blocked_channel",
                        "message": (
                            f"This command cannot be executed via the {channel_name} interface "
                            "for security reasons. Please use the TUI (`agens tui`) to run it."
                        ),
                    }

                # ── Windows: block sudo everywhere ──────────────────────────
                if is_sudo and platform.system() == "Windows":
                    logger.info(
                        "Sudo command blocked on Windows: tool=%s session=%s",
                        name, session_id,
                    )
                    return {
                        "status": "blocked_platform",
                        "message": (
                            "Privileged execution (sudo) is not supported on Windows. "
                            "Please run this command in a Linux/macOS environment or WSL."
                        ),
                    }

                # ── Safety mode ON: block regardless of channel ──────────────
                if safety_mode:
                    logger.info(
                        "Command blocked by safety mode: tool=%s session=%s",
                        name, session_id,
                    )
                    return {
                        "status": "blocked",
                        "message": (
                            "Safety mode is ON. This command is blocked and cannot be executed "
                            "through the assistant. Disable safety mode in Settings to enable "
                            "dangerous command execution."
                        ),
                    }

                # ── TUI: execute inline ──────────────────────────────────────
                if is_sudo:
                    if sudo_password_provider is None:
                        return {
                            "status": "blocked_channel",
                            "message": (
                                "Sudo commands cannot be executed via this interface for security reasons. "
                                "Please use the TUI (`agens tui`) to run this command."
                            ),
                        }

                    password = await sudo_password_provider()
                    if password is None:
                        logger.info("Sudo password prompt cancelled: session=%s", session_id)
                        return {
                            "status": "cancelled",
                            "message": "Sudo authorization cancelled. The command was not executed.",
                        }

                    confirmed_args = {
                        **args,
                        "confirmed": True,
                        "use_sudo": True,
                        "sudo_password": password,
                    }
                else:
                    confirmed_args = {**args, "confirmed": True}

                logger.info(
                    "Executing dangerous command inline (TUI): tool=%s session=%s",
                    name, session_id,
                )
                return await self._execute_tool(name, confirmed_args)

            return result
        # ────────────────────────────────────────────────────────────────────────

        for attempt in range(max_retries):
            answer_parts.clear()
            last_done_event = None
            stream_error: str | None = None

            try:
                if (
                    selected_provider
                    and not selected_provider_bound
                    and self._llm.config.name != selected_provider
                ):
                    bound = await self._router.pick_next(preferred=preferred_model_ref)
                    if bound is None:
                        raise LLMUnavailableError(
                            f"No available keys for provider={selected_provider} model={active_model}"
                        )
                    self._llm = bound.client
                    self._current_key_id = bound.key_id
                    self.model_name = bound.entry.id
                    active_model = bound.entry.id
                    selected_provider_bound = True
                    yield StreamEvent(
                        type="status",
                        message=f"Model set to {bound.entry.name}.",
                    )

                # Pre-flight key check — swap key if current one is cooling down.
                swapped, active_model = await self._ensure_key_available(
                    active_model, api_key_manager, db
                )
                if swapped:
                    yield StreamEvent(
                        type="status",
                        message="API key rotated. Proceeding with the request.",
                    )

                async for event in self._llm.react_stream(
                    messages=messages,
                    model=active_model,
                    tool_schemas=tool_schemas,
                    tool_executor=_gated_tool_executor,
                ):
                    if event.type == "error":
                        stream_error = event.error or "Unknown LLM stream error"
                        break
                    if event.type == "token" and event.content:
                        answer_parts.append(event.content)
                    if event.type == "done":
                        last_done_event = event
                        continue
                    yield event

                if stream_error:
                    is_empty_stop = (
                        stream_error.startswith("No content. Finish reason:")
                        and "STOP" in stream_error
                    )
                    if is_empty_stop and attempt < max_retries - 1:
                        logger.warning(
                            "Empty LLM response on attempt %d/%d; retrying",
                            attempt + 1,
                            max_retries,
                        )
                        yield StreamEvent(type="status", message="Empty response. Retrying.")
                        continue

                    yield StreamEvent(type="error", error=stream_error)
                    return

                # Persist the conversation before yielding the final event.
                full_answer = "".join(answer_parts)
                if full_answer and last_done_event:
                    tool_calls_json = [
                        {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result, "error": tc.error}
                        for tc in last_done_event.tool_calls
                    ]
                    await memory_manager.store(session_id, user_request, full_answer, tool_calls_json)

                if last_done_event:
                    yield last_done_event

                break

            except RateLimitError as e:
                current_model = active_model
                logger.warning(
                    "Rate limit on attempt %d: provider=%s model=%s retry_after=%ds daily=%s",
                    attempt,
                    self._llm.config.name,
                    current_model,
                    e.retry_after,
                    e.is_daily,
                )
                if self._current_key_id is None:
                    yield StreamEvent(
                        type="error",
                        error="No active API key is bound to this request.",
                    )
                    return

                try:
                    new_config = await api_key_manager.rotate_key(
                        provider=self._llm.config.name,
                        model=current_model,
                        error=e,
                        current_key_id=self._current_key_id,
                        db=db,
                    )
                    if new_config is None:
                        raise LLMUnavailableError(
                            "All API keys are exhausted across all providers."
                        )

                    self._llm.swap_key(new_config)
                    self._current_key_id = api_key_manager.last_rotated_key_id
                    active_model = new_config.default_model
                    self.model_name = active_model
                    logger.info(
                        "Rotated to provider=%s model=%s",
                        new_config.name,
                        active_model,
                    )
                    yield StreamEvent(
                        type="status",
                        message=f"Switched to {new_config.name}. Retrying.",
                    )
                    if attempt < max_retries - 1:
                        continue
                    yield StreamEvent(
                        type="error",
                        error=f"Retry budget exhausted. Last tried: {current_model}.",
                    )
                    return
                except LLMUnavailableError as e2:
                    yield StreamEvent(type="error", error=str(e2))
                    return

            except LLMError as e:
                is_auth_error = getattr(e, "is_auth_error", False)
                is_transient = getattr(e, "is_transient", False)

                if not (is_auth_error or is_transient):
                    logger.warning("LLM error on attempt %d: %s", attempt, e)
                    yield StreamEvent(type="error", error=str(e))
                    return

                if self._current_key_id is None:
                    yield StreamEvent(
                        type="error",
                        error="No active API key is bound to this request.",
                    )
                    return

                if is_auth_error:
                    logger.error(
                        "Deactivating revoked API key: %s",
                        self._current_key_id,
                    )
                    await api_key_manager.deactivate(self._current_key_id)
                else:
                    logger.warning(
                        "Key %s hit transient error (%s). Cooling down.",
                        self._current_key_id,
                        e,
                    )
                    await api_key_manager.repo.set_model_cooldown(
                        key_id=self._current_key_id,
                        model=active_model,
                        reason="rate_limit",
                        duration_seconds=transient_cooldown_seconds,
                    )

                try:
                    new_config = await _pick_next_config(
                        self._llm.config.name,
                        active_model,
                    )
                except Exception as rotate_error:
                    logger.warning(
                        "Key rotation failed after LLM error: %s",
                        rotate_error,
                        exc_info=True,
                    )
                    yield StreamEvent(type="error", error=str(e))
                    return

                if new_config is None:
                    if is_auth_error:
                        yield StreamEvent(
                            type="error",
                            error="The API key is invalid or has been revoked. It has been deactivated. Please configure a valid API key in Settings.",
                        )
                    else:
                        yield StreamEvent(
                            type="error",
                            error="All API keys are exhausted across all providers.",
                        )
                    return

                self._llm.swap_key(new_config)
                self._current_key_id = api_key_manager.last_rotated_key_id
                active_model = new_config.default_model
                self.model_name = active_model
                status_msg = (
                    "Authentication error. Switched API keys."
                    if is_auth_error
                    else "Transient provider error. Switched API keys."
                )
                yield StreamEvent(type="status", message=status_msg)
                if attempt < max_retries - 1:
                    continue
                yield StreamEvent(
                    type="error",
                    error=f"Retry budget exhausted. Last tried: {active_model}.",
                )
                return

            except Exception as e:
                logger.error("Streaming ReAct loop failed: %s", e, exc_info=True)
                yield StreamEvent(type="error", error=str(e))
                return

        if retry_exhausted_error:
            yield StreamEvent(type="error", error=retry_exhausted_error)
            return

    async def _ensure_key_available(
        self,
        model: str,
        api_key_manager: APIKeyManager,
        db: AsyncSession,
    ) -> tuple[bool, str]:
        """
        Check if the current key is cooling down for this model.
        If so, find and swap to an available key.

        Returns (swapped, active_model). The active model can change when the
        replacement key belongs to a different provider.
        """
        from llm.providers import build_provider_config

        repo = APIKeyRepository(db)

        if self._current_key_id is None:
            available = await repo.pick_available_key(self._llm.config.name, model)
            if available is None:
                available = await repo.pick_available_key(None, None)
            if available is None:
                raise LLMUnavailableError(
                    "No available keys for any provider."
                )
            raw_key = api_key_manager.fernet.decrypt(available.encrypted_key.encode()).decode()
            new_config = build_provider_config(available.provider, api_key=raw_key)
            self._llm.swap_key(new_config)
            self._current_key_id = available.id
            self.model_name = new_config.default_model
            logger.info(
                "Pre-flight: swapped to provider=%s model=%s",
                new_config.name,
                new_config.default_model,
            )
            return True, new_config.default_model

        is_available = await api_key_manager.is_model_available_for_key(
            self._current_key_id,
            model,
        )
        if is_available:
            return False, model

        logger.info("Current key unavailable for model=%s, finding backup...", model)
        available = await repo.pick_available_key(self._llm.config.name, model)
        if available is None:
            available = await repo.pick_available_key(None, None)
        if available is None:
            raise LLMUnavailableError(
                "No available keys for any provider."
            )

        raw_key = api_key_manager.fernet.decrypt(
            available.encrypted_key.encode()
        ).decode()
        new_config = build_provider_config(available.provider, api_key=raw_key)
        self._llm.swap_key(new_config)
        self._current_key_id = available.id
        self.model_name = new_config.default_model
        logger.info(
            "Pre-flight: swapped to provider=%s model=%s",
            new_config.name,
            new_config.default_model,
        )
        return True, new_config.default_model

    async def _ensure_model_available(
        self,
        model: str,
        api_key_manager: APIKeyManager,
        db: AsyncSession,
        preferred: str | None = None,
    ) -> bool:
        """Pre-flight check. Returns True if we swapped to a new model/key."""
        if self._current_key_id is None:
            bound = await self._router.pick_next(preferred=preferred or model)
            if bound is None:
                raise LLMUnavailableError("No free-tier keys available.")
            self._llm = bound.client
            self._current_key_id = bound.key_id
            self.model_name = bound.entry.id
            return True

        is_ok = await api_key_manager.is_model_available_for_key(
            self._current_key_id, model
        )
        if is_ok:
            return False

        bound = await self._router.pick_next(preferred=preferred or model, exclude={model})
        if bound is None:
            raise LLMUnavailableError(f"No backup models available for {model}.")
        self._llm = bound.client
        self._current_key_id = bound.key_id
        self.model_name = bound.entry.id
        return True

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        if inspect.iscoroutinefunction(tool.execute):
            return await tool.execute(**args)
        else:
            return await asyncio.to_thread(tool.execute, **args)
