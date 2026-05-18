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
from llm.errors import RateLimitError, LLMUnavailableError
from llm.router import FreeTierRouter
from core.tool_groups import get_enabled_tool_names, get_enabled_tool_schemas
from core.registry import ToolRegistry
from core.types import (
    CONFIRMATION_TTL_SECONDS,
    PendingConfirmation,
    StreamEvent,
)
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager
from services.api_key_manager import APIKeyManager
from services.settings_service import SettingsService
from tools.search_web import SearchUnavailableError
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
        router: FreeTierRouter,
        config_manager: ConfigManager,
        fernet: Fernet,
    ) -> None:
        self._registry = registry
        self._llm = llm
        self._router = router
        self._current_key_id: str | None = getattr(llm, "current_key_id", None)
        self.model_name = llm.config.default_model
        self._config_manager = config_manager
        self._fernet = fernet
        # Keyed by session_id. One pending confirmation per session at a time.
        # In-memory only — cleared on server restart (by design).
        self._pending_confirmations: dict[str, PendingConfirmation] = {}

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
                try:
                    asyncio.get_running_loop().create_task(_close_db())
                except RuntimeError:
                    pass



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

        # ── Confirmation gate — evaluated BEFORE the LLM is ever invoked ────────
        # pop() atomically removes the pending entry so a second "YES" is a no-op.
        pending = self._pending_confirmations.pop(session_id, None)
        if pending is not None:
            if pending.tool_name not in enabled_tool_names:
                msg = (
                    f"Action cancelled. The tool '{pending.tool_name}' is disabled "
                    "for this chat session."
                )
                logger.info(
                    "Pending confirmation cancelled by disabled tool: session=%s tool=%s",
                    session_id,
                    pending.tool_name,
                )
                yield StreamEvent(type="confirmation_result", message=msg)
                yield StreamEvent(type="token", content=msg)
                await memory_manager.store(session_id, user_request, msg, [])
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
                return

            elapsed = time.time() - pending.created_at
            if elapsed > CONFIRMATION_TTL_SECONDS:
                # Confirmation window has expired.
                msg = (
                    f"Confirmation expired after {int(elapsed)}s "
                    f"(limit: {CONFIRMATION_TTL_SECONDS}s). Action cancelled. "
                    "Please re-request if you still want to run the command."
                )
                logger.info("Confirmation TTL expired for session=%s", session_id)
                yield StreamEvent(type="confirmation_result", message=msg)
                yield StreamEvent(type="token", content=msg)
                await memory_manager.store(session_id, user_request, msg, [])
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
                return

            normalized_confirmation = user_request.strip().upper()
            is_confirmed = normalized_confirmation == "YES" or (
                channel == Channel.TUI and normalized_confirmation == "Y"
            )
            if is_confirmed:
                # Check if this is a sudo command that needs a password (TUI only).
                use_sudo = bool(pending.arguments.get("use_sudo", False))
                if use_sudo:
                    if sudo_password_provider is None:
                        # Web/Telegram should never reach here — but guard anyway.
                        msg = (
                            "Sudo commands cannot be executed via this interface for security reasons. "
                            "Please use the TUI (`agens tui`) to run this command."
                        )
                        yield StreamEvent(type="confirmation_result", message=msg)
                        yield StreamEvent(type="token", content=msg)
                        await memory_manager.store(session_id, user_request, msg, [])
                        yield StreamEvent(type="done", tool_calls=[], next_action=None)
                        return

                    # Prompt the user for their sudo password (TUI callback).
                    password = await sudo_password_provider()
                    if password is None:
                        # User cancelled the password prompt.
                        msg = "Sudo authorization cancelled. The command was not executed."
                        logger.info("Sudo password prompt cancelled: session=%s", session_id)
                        yield StreamEvent(type="confirmation_result", message=msg)
                        yield StreamEvent(type="token", content=msg)
                        await memory_manager.store(session_id, user_request, msg, [])
                        yield StreamEvent(type="done", tool_calls=[], next_action=None)
                        return

                    confirmed_args = {
                        **pending.arguments,
                        "confirmed": True,
                        "use_sudo": True,
                        "sudo_password": password,
                    }
                else:
                    confirmed_args = {**pending.arguments, "confirmed": True}

                logger.info(
                    "User confirmed dangerous command: tool=%s session=%s",
                    pending.tool_name, session_id,
                )
                status_msg = f"Executing confirmed command: `{pending.command_preview}`"
                yield StreamEvent(type="status", message=status_msg)
                tool_call_record: dict = {
                    "tool": pending.tool_name,
                    "arguments": pending.arguments,
                    "result": None,
                    "error": None,
                }
                try:
                    result = await self._execute_tool(pending.tool_name, confirmed_args)
                    tool_call_record["result"] = result
                    yield StreamEvent(
                        type="confirmation_result",
                        tool=pending.tool_name,
                        result=result,
                    )
                    stdout = result.get("stdout", "").strip()
                    stderr = result.get("stderr", "").strip()
                    exit_code = result.get("exit_code", "n/a")
                    output_section = stdout or stderr or "_No output._"
                    answer = (
                        f"✅ **Command executed successfully.**\n\n"
                        f"```\n$ {pending.command_preview}\n```\n\n"
                        f"**Exit code:** `{exit_code}`\n\n"
                        f"**Output:**\n```\n{output_section}\n```"
                    )
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    tool_call_record["error"] = error_msg
                    logger.error("Confirmed command failed: %s", error_msg)
                    yield StreamEvent(
                        type="confirmation_result",
                        tool=pending.tool_name,
                        error=error_msg,
                    )
                    answer = (
                        f"❌ **Command failed.**\n\n"
                        f"```\n$ {pending.command_preview}\n```\n\n"
                        f"**Error:** `{error_msg}`"
                    )

                yield StreamEvent(type="token", content=answer)
                await memory_manager.store(
                    session_id, user_request, answer, [tool_call_record]
                )
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
                return

            else:
                # Anything other than "YES" cancels the action.
                cancel_msg = (
                    "Action cancelled. The command was not executed. "
                    "Reply with your next request."
                )
                logger.info(
                    "User declined dangerous command: session=%s input=%r",
                    session_id, user_request[:50],
                )
                yield StreamEvent(type="confirmation_result", message=cancel_msg)
                yield StreamEvent(type="token", content=cancel_msg)
                await memory_manager.store(session_id, user_request, cancel_msg, [])
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
                return
        # ── End confirmation gate ──────────────────────────────────────────────────

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

        # ── Gated tool executor ──────────────────────────────────────────────────
        # Wraps self._execute_tool to intercept needs_confirmation responses.
        # If a tool requests confirmation, we store the PendingConfirmation and
        # stop the stream immediately after the current tool event. The UI renders
        # the confirmation prompt directly;
        captured_confirmation: list[PendingConfirmation] = []  # max length 1

        async def _emit_pending_confirmation(
            pending_conf: PendingConfirmation,
            tool_calls: list[dict],
        ) -> AsyncIterator[StreamEvent]:
            logger.info(
                "Stored pending confirmation: session=%s tool=%s",
                session_id, pending_conf.tool_name,
            )
            yield StreamEvent(
                type="confirmation_required",
                tool=pending_conf.tool_name,
                arguments=pending_conf.arguments,
                confirmation_reason=pending_conf.reason,
                confirmation_preview=pending_conf.command_preview,
            )
            await memory_manager.store(
                session_id,
                user_request,
                "".join(answer_parts),
                tool_calls,
            )
            yield StreamEvent(type="done", tool_calls=[], next_action="await_confirmation")

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

                # ── Web & Telegram: block sudo commands entirely ─────────────
                if is_sudo and channel in (Channel.WEB, Channel.TELEGRAM):
                    channel_name = "web" if channel == Channel.WEB else "Telegram"
                    logger.info(
                        "Sudo command blocked on %s: tool=%s session=%s",
                        channel_name, name, session_id,
                    )
                    return {
                        "status": "blocked_channel",
                        "message": (
                            "Sudo commands cannot be executed via the "
                            f"{channel_name} interface for security reasons. "
                            "Please use the TUI (`agens tui`) to run this command."
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

                if channel == Channel.TELEGRAM:
                    # Telegram blocks ALL confirmation-required commands.
                    logger.info(
                        "Confirmation-required command blocked on telegram: tool=%s session=%s",
                        name, session_id,
                    )
                    return {
                        "status": "blocked_channel",
                        "message": (
                            "This command requires confirmation, which is not supported "
                            "over Telegram for security reasons. Please use the web or "
                            "terminal interface to run this command."
                        ),
                    }

                elif channel == Channel.TUI:
                    # In TUI, use a lightweight y/N flow.
                    pending_args = {**args, "use_sudo": True} if is_sudo else args
                    confirmation = PendingConfirmation(
                        tool_name=name,
                        arguments=pending_args,
                        reason=result["reason"],
                        command_preview=result["preview"],
                        created_at=time.time(),
                        session_id=session_id,
                    )
                    self._pending_confirmations[session_id] = confirmation
                    captured_confirmation.append(confirmation)
                    logger.info(
                        "Confirmation-required command queued for TUI: tool=%s session=%s command=%r",
                        name, session_id, result["preview"],
                    )
                    return {
                        "status": "awaiting_user_confirmation",
                        "reason": result["reason"],
                        "preview": result["preview"],
                    }

                elif safety_mode:
                    # Safety mode ON — permanently block; no path to execution.
                    logger.info(
                        "Command blocked by safety mode: tool=%s session=%s",
                        name, session_id,
                    )
                    return {
                        "status": "blocked",
                        "message": (
                            "Safety mode is ON. This command is blocked and cannot be executed "
                            "through the assistant. Disable safety mode in Settings to enable "
                            "the confirmation flow."
                        ),
                    }

                # Safety mode OFF on Web — normal confirmation flow (non-sudo only).
                confirmation = PendingConfirmation(
                    tool_name=name,
                    arguments=args,
                    reason=result["reason"],
                    command_preview=result["preview"],
                    created_at=time.time(),
                    session_id=session_id,
                )
                self._pending_confirmations[session_id] = confirmation
                captured_confirmation.append(confirmation)
                logger.info(
                    "Dangerous command intercepted: tool=%s session=%s command=%r",
                    name, session_id, result["preview"],
                )
                return {
                    "status": "awaiting_user_confirmation",
                    "reason": result["reason"],
                    "preview": result["preview"],
                }

            return result
        # ────────────────────────────────────────────────────────────────────────────────

        for attempt in range(max_retries):
            answer_parts.clear()
            last_done_event = None
            stream_error: str | None = None
            active_model = model_name or self._llm.config.default_model

            try:
                if selected_provider and self._llm.config.name != selected_provider:
                    bound = await self._router.pick_next(preferred=preferred_model_ref)
                    if bound is None:
                        raise LLMUnavailableError(
                            f"No available keys for provider={selected_provider} model={active_model}"
                        )
                    self._llm = bound.client
                    self._current_key_id = bound.key_id
                    self.model_name = bound.entry.id
                    yield StreamEvent(
                        type="status",
                        message=f"Model set to {bound.entry.name}.",
                    )

                # Pre-flight key check — swap key if current one is cooling down.
                swapped = await self._ensure_model_available(
                    active_model, api_key_manager, db, preferred=preferred_model_ref
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

                    if captured_confirmation:
                        pending_conf = captured_confirmation[0]
                        tool_calls_json: list[dict] = []
                        if event.type == "tool_end" and event.tool == pending_conf.tool_name:
                            tool_calls_json.append(
                                {
                                    "tool": pending_conf.tool_name,
                                    "arguments": pending_conf.arguments,
                                    "result": {
                                        "status": "awaiting_user_confirmation",
                                        "reason": pending_conf.reason,
                                        "preview": pending_conf.command_preview,
                                    },
                                    "error": event.error,
                                }
                            )
                        async for confirmation_event in _emit_pending_confirmation(
                            pending_conf,
                            tool_calls_json,
                        ):
                            yield confirmation_event
                        return

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
                current_model = self.model_name or self._llm.config.default_model
                logger.warning(
                    "Rate limit on attempt %d: model=%s", attempt, current_model
                )

                # 1. Smart cooldown via catalog
                from llm.catalog import get_model, cooldown_for
                entry = get_model(current_model)
                cooldown_sec = cooldown_for(entry, "rate_limit") if entry else 60
                if self._current_key_id:
                    await api_key_manager.repo.set_model_cooldown(
                        self._current_key_id,
                        current_model,
                        reason="rate_limit",
                        duration_seconds=cooldown_sec,
                    )

                # 2. Cross-provider fallback via router
                bound = await self._router.pick_next(
                    preferred=preferred_model_ref or model_name,  # user override if any
                    exclude={current_model},
                )
                if bound:
                    self._llm = bound.client
                    self._current_key_id = bound.key_id
                    self.model_name = bound.entry.id
                    yield StreamEvent(
                        type="status",
                        message=f"Rate limited on {current_model}. "
                                f"Falling back to {bound.entry.name}.",
                    )
                    if attempt < max_retries - 1:
                        continue   # retry the react_stream with new client
                # 3. Truly exhausted
                yield StreamEvent(
                    type="error",
                    error=f"All free-tier models are rate-limited. "
                          f"Last tried: {current_model}.",
                )
                return

            except LLMUnavailableError as e:
                logger.warning("LLM unavailable on attempt %d: %s", attempt, e)
                yield StreamEvent(type="error", error=str(e))
                return

            except SearchUnavailableError as e:
                yield StreamEvent(type="token", content=str(e))
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
    ) -> bool:
        """
        Check if the current key is cooling down for this model.
        If so, find and swap to an available key.
        """
        repo = APIKeyRepository(db)

        if self._current_key_id is None:
            available = await repo.pick_available_key(self._llm.config.name, model)
            if available is None:
                raise LLMUnavailableError(
                    f"No available keys for provider={self._llm.config.name} model={model}"
                )
            raw_key = api_key_manager.fernet.decrypt(available.encrypted_key.encode()).decode()
            self._llm.swap_key(raw_key)
            self._current_key_id = available.id
            self.model_name = self._llm.config.default_model
            return True

        is_available = await api_key_manager.is_model_available_for_key(
            self._current_key_id,
            model,
        )
        if is_available:
            return False

        logger.info("Current key cooling down for model=%s, finding backup...", model)
        available = await repo.pick_available_key(self._llm.config.name, model)
        if available is None:
            raise LLMUnavailableError(
                f"No available keys for provider={self._llm.config.name} model={model}"
            )

        raw_key = api_key_manager.fernet.decrypt(
            available.encrypted_key.encode()
        ).decode()
        self._llm.swap_key(raw_key)
        self._current_key_id = available.id
        self.model_name = self._llm.config.default_model
        logger.info("Pre-flight: swapped to backup key for model=%s", model)
        return True


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
