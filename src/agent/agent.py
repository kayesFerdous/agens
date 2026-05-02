from __future__ import annotations

import asyncio
import inspect
import time

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.logging import get_logger
from typing import Any, AsyncIterator
from db.repositories.api_key import APIKeyRepository
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import CONFIRMATION_TTL_SECONDS, PendingConfirmation, StreamEvent
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager
from llm.llm_exceptions import RateLimitError, LLMUnavailable
from services.api_key_manager import APIKeyManager
from tools.search_web import SearchUnavailableError
from db.database import async_session

logger = get_logger(__name__)


class Agent:
    def __init__(
        self,
        registry: ToolRegistry,
        llm: LLM,
        config_manager: ConfigManager,
        fernet: Fernet,
    ) -> None:
        self._registry = registry
        self._llm = llm
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
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """Unified streaming entry point for web, telegram, and TUI adapters.

        Opens its own DB session so callers don't manage transactions.
        """
        async with async_session() as db:
            async for event in self.run_stream(message, session_id, db, model=model):
                yield event


    async def run(self, user_request: str, session_id: str, db: AsyncSession) -> str:
        """Non-streaming ReAct loop. Returns the final text answer.

        Uses per-model cooldowns: on RateLimitError, only the failing model is
        marked on cooldown and we switch to another key that can still serve it.
        """
        memory_manager = MemoryManager(db)
        system = build_system_prompt(self._config_manager)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        provider = "gemini"
        api_key_manager = APIKeyManager(repo=APIKeyRepository(db), fernet=self._fernet)
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # Pre-flight: ensure the current key is usable for this model, and swap if not
                model = self._llm.model_name
                await self._llm.ensure_model_key(db, model, api_key_manager)

                answer = await self._llm.react(
                    user_request,
                    system=system,
                    tool_schemas=tool_schemas,
                    tool_executor=self._execute_tool,
                    message_history=message_history,
                )
                await api_key_manager.on_success(self._llm.current_key_id)
                await memory_manager.store(session_id, user_request, answer, [])
                return answer

            except RateLimitError as e:
                logger.warning(
                    "Rate limit on attempt %d: key=%s model=%s daily=%s",
                    attempt, e.key_id, model, e.is_daily,
                )
                try:
                    await self._llm.handle_model_error(db, model, e, api_key_manager)
                except LLMUnavailable:
                    raise RuntimeError(
                        f"All API keys are on cooldown for model '{model}'."  
                    )

            except LLMUnavailable as e:
                logger.warning("LLM unavailable on attempt %d: %s", attempt, e)
                raise RuntimeError(str(e))

        raise RuntimeError("Max retries reached without a successful response.")

    async def run_stream(
        self,
        user_request: str,
        session_id: str,
        db: AsyncSession,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        memory_manager = MemoryManager(db)

        # ── Confirmation gate — evaluated BEFORE the LLM is ever invoked ────────
        # pop() atomically removes the pending entry so a second "YES" is a no-op.
        pending = self._pending_confirmations.pop(session_id, None)
        if pending is not None:
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
                yield StreamEvent(type="done", tool_calls=[])
                await memory_manager.store(session_id, user_request, msg, [])
                return

            if user_request.strip().upper() == "YES":
                # User explicitly approved — execute with the bypass flag.
                logger.info(
                    "User confirmed dangerous command: tool=%s session=%s",
                    pending.tool_name, session_id,
                )
                status_msg = f"Executing confirmed command: `{pending.command_preview}`"
                yield StreamEvent(type="status", message=status_msg)

                confirmed_args = {**pending.arguments, "confirmed": True}
                try:
                    result = await self._execute_tool(pending.tool_name, confirmed_args)
                    yield StreamEvent(
                        type="confirmation_result",
                        tool=pending.tool_name,
                        result=result,
                    )
                    answer = (
                        f"Confirmed command executed.\n"
                        f"Command: `{pending.command_preview}`\n"
                        f"Exit code: {result.get('exit_code', 'n/a')}\n"
                        f"Output: {result.get('stdout', '') or result.get('error', '')}"
                    )
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {e}"
                    logger.error("Confirmed command failed: %s", error_msg)
                    yield StreamEvent(
                        type="confirmation_result",
                        tool=pending.tool_name,
                        error=error_msg,
                    )
                    answer = f"Confirmed command failed: {error_msg}"

                yield StreamEvent(type="done", tool_calls=[])
                await memory_manager.store(session_id, user_request, answer, [])
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
                yield StreamEvent(type="done", tool_calls=[])
                await memory_manager.store(session_id, user_request, cancel_msg, [])
                return
        # ── End confirmation gate ──────────────────────────────────────────────────

        system = build_system_prompt(self._config_manager)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        model_name = None
        if model:
            _, model_name = model.split("/", maxsplit=1)

        # provider = "gemini"  # TODO: derive from model prefix when multi-provider support lands
        api_key_manager = APIKeyManager(repo=APIKeyRepository(db), fernet=self._fernet)

        answer_parts: list[str] = []
        last_done_event: StreamEvent | None = None
        max_retries = 3

        # ── Gated tool executor ──────────────────────────────────────────────────
        # Wraps self._execute_tool to intercept needs_confirmation responses.
        # If a tool requests confirmation, we store the PendingConfirmation and
        # return a synthetic message to the LLM so it explains the situation to
        # the user and stops calling tools.
        captured_confirmation: list[PendingConfirmation] = []  # max length 1

        async def _gated_tool_executor(name: str, args: dict[str, Any]) -> dict[str, Any]:
            result = await self._execute_tool(name, args)

            if result.get("status") == "needs_confirmation":
                confirmation = PendingConfirmation(
                    tool_name=name,
                    arguments=args,
                    reason=result["reason"],
                    command_preview=result["preview"],
                    created_at=time.time(),
                    session_id=session_id,
                )
                captured_confirmation.append(confirmation)
                logger.info(
                    "Dangerous command intercepted: tool=%s session=%s command=%r",
                    name, session_id, result["preview"],
                )
                # Return a synthetic result to the LLM so it knows to
                # warn the user and not attempt further tool calls.
                return {
                    "status": "awaiting_user_confirmation",
                    "message": (
                        f"\u26a0\ufe0f This command requires explicit user confirmation before execution.\n"
                        f"Reason: {result['reason']}\n"
                        f"Command: `{result['preview']}`\n\n"
                        "Explain the risk to the user and ask them to reply exactly 'YES' to proceed, "
                        "or anything else to cancel. Do NOT attempt to call this tool again."
                    ),
                }

            return result
        # ────────────────────────────────────────────────────────────────────────────────

        for attempt in range(max_retries):
            answer_parts.clear()
            last_done_event = None

            # The active model may be overridden per-request via the model_name arg.
            active_model = model_name or self._llm.model_name

            try:
                # Pre-flight: ensure the current key is usable for this model, and swap if not
                swapped = await self._llm.ensure_model_key(db, active_model, api_key_manager)
                if swapped:
                    yield StreamEvent(
                        type="status",
                        message="API key rotated. Proceeding with the request.",
                    )

                async for event in self._llm.react_stream(
                    user_request,
                    system=system,
                    tool_schemas=tool_schemas,
                    tool_executor=_gated_tool_executor,  # ← gated wrapper, not self._execute_tool
                    message_history=message_history,
                    model_name=model_name,
                ):
                    if event.type == "token" and event.content:
                        answer_parts.append(event.content)
                    if event.type == "done":
                        last_done_event = event
                    yield event

                # ✅ Clean exit — record usage and reset failure counters.
                # await api_key_manager.on_success(self._llm.current_key_id) #INFO: Doesn't adding any value right now
                break

            except RateLimitError as e:
                logger.warning(
                    "Stream rate limit on attempt %d: key=%s model=%s daily=%s",
                    attempt, e.key_id, active_model, e.is_daily,
                )
                try:
                    await self._llm.handle_model_error(db, active_model, e, api_key_manager)
                    yield StreamEvent(
                        type="status",
                        message="API key rotated for this model. Retrying the request.",
                    )
                except LLMUnavailable:
                    yield StreamEvent(
                        type="error",
                        error=f"All API keys are on cooldown for model '{active_model}'.",
                    )
                    return

            except LLMUnavailable as e:
                logger.warning("LLM unavailable on attempt %d: %s", attempt, e)
                yield StreamEvent(type="error", error=str(e))
                return

            except SearchUnavailableError as e:
                yield StreamEvent(type="token", content=str(e))
                return

            except Exception as e:
                logger.error("Streaming ReAct loop failed: %s", e)
                yield StreamEvent(type="error", error=str(e))
                return

            finally:
                full_answer = "".join(answer_parts)
                if full_answer and last_done_event:
                    tool_calls_json = [
                        {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result, "error": tc.error}
                        for tc in last_done_event.tool_calls
                    ]
                    await memory_manager.store(session_id, user_request, full_answer, tool_calls_json)

        # ── Emit confirmation_required AFTER the ReAct loop has cleanly exited ──────
        # The LLM has already produced its warning message (streamed above).
        # This event carries the structured metadata for the UI to render a
        # confirmation prompt, and stores the action for the next message.
        if captured_confirmation:
            pending_conf = captured_confirmation[0]
            self._pending_confirmations[session_id] = pending_conf
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

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        if inspect.iscoroutinefunction(tool.execute):
            return await tool.execute(**args)
        else:
            return await asyncio.to_thread(tool.execute, **args)
