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
from core.types import (
    CONFIRMATION_TTL_SECONDS,
    SUDO_AUTHORIZATION_TTL_SECONDS,
    PendingConfirmation,
    StreamEvent,
)
from config.settings import settings
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
        # Keyed by session_id, value is time.time() when authorized.
        # Single-use: consumed immediately after one sudo command executes.
        self._sudo_authorized_sessions: dict[str, float] = {}

    # ------------------------------------------------------------------
    # Sudo authorization helpers (never touch LLM context or message history)
    # ------------------------------------------------------------------

    def _is_sudo_authorized(self, session_id: str) -> bool:
        """True if session has a valid, non-expired sudo authorization."""
        authorized_at = self._sudo_authorized_sessions.get(session_id)
        if authorized_at is None:
            return False
        if time.time() - authorized_at > SUDO_AUTHORIZATION_TTL_SECONDS:
            self._sudo_authorized_sessions.pop(session_id, None)  # prune stale entry
            return False
        return True

    def _consume_sudo_authorization(self, session_id: str) -> None:
        """Single-use: remove authorization immediately after one sudo command executes."""
        self._sudo_authorized_sessions.pop(session_id, None)

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

        DB lifecycle:
        - Normal path: session is closed via ``await`` before the terminal
          ``done``/``error`` event is yielded.  The close runs while the anyio
          task is still active so it always succeeds.
        - Cancelled path (client disconnects mid-stream): the ASGI task is
          cancelled by anyio before we reach a terminal event.  Any ``await``
          inside the cancelled scope raises ``CancelledError``, including those
          inside ``anyio.CancelScope(shield=True)`` when the generator is being
          finalized by the GC outside any anyio task context.  We escape this by
          scheduling ``db.close()`` as an *independent* asyncio task that is not
          a child of the ASGI task and is therefore not subject to its cancel
          scope.
        """
        db = async_session()
        session_closed = False

        async def _close_db() -> None:
            nonlocal session_closed
            if not session_closed:
                session_closed = True
                try:
                    await db.close()
                except Exception:
                    pass  # Nothing useful we can do here; NullPool discards it

        try:
            async for event in self.run_stream(message, session_id, db, model=model):
                if event.type in ("done", "error"):
                    # Eagerly close BEFORE yielding the terminal event.
                    # The anyio task is still active at this point, so the await
                    # works normally. After the frontend receives 'done' it closes
                    # the SSE connection which cancels the task — by then there is
                    # nothing left to clean up.
                    await _close_db()
                yield event
        finally:
            if not session_closed:
                # Cancelled path: we are inside a dead anyio scope — any await
                # here will raise CancelledError immediately.  Detach the close
                # onto an independent asyncio task that the event loop will run
                # after the current (cancelled) task is torn down.
                try:
                    asyncio.get_running_loop().create_task(_close_db())
                except RuntimeError:
                    pass  # No running loop at all (server shutting down)


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
                yield StreamEvent(type="token", content=msg)
                # Store BEFORE yielding done — chat() closes the DB the moment
                # it sees the done event, so any await after that is on a dead session.
                await memory_manager.store(session_id, user_request, msg, [])
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
                return

            if user_request.strip().upper() == "YES":
                # User explicitly approved — but sudo commands need a second factor.
                if pending.requires_sudo_auth:
                    if not self._is_sudo_authorized(session_id):
                        # Authorization not present or expired — ask frontend to prompt.
                        logger.info(
                            "sudo_auth_required: session=%s command=%r",
                            session_id, pending.command_preview,
                        )
                        # Re-store the pending confirmation so the user can retry after authorizing.
                        self._pending_confirmations[session_id] = pending
                        yield StreamEvent(
                            type="sudo_auth_required",
                            confirmation_preview=pending.command_preview,
                        )
                        yield StreamEvent(type="done", tool_calls=[], next_action="await_sudo_auth")
                        return

                    # Authorization valid — consume it (single-use) before executing.
                    self._consume_sudo_authorization(session_id)
                    confirmed_args = {**pending.arguments, "confirmed": True, "use_sudo": True}
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
                # Store BEFORE yielding done — chat() closes the DB the moment it
                # sees the done event, so any await after that is on a dead session.
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
                # Store BEFORE yielding done — same DB lifecycle reason as above.
                await memory_manager.store(session_id, user_request, cancel_msg, [])
                yield StreamEvent(type="done", tool_calls=[], next_action=None)
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
                if settings.SAFETY_MODE_ENABLED:
                    # Safety mode ON — permanently block; no path to execution.
                    logger.info(
                        "sudo blocked by safety mode: tool=%s session=%s",
                        name, session_id,
                    )
                    return {
                        "status": "blocked",
                        "message": (
                            "Safety mode is ON. This command is blocked and cannot be executed "
                            "through the assistant. Disable safety mode in .env to enable "
                            "the authorization flow."
                        ),
                    }

                # Safety mode OFF — flag whether this command needs sudo authorization.
                # Re-use _NEEDS_CONFIRMATION from the tool module so detection stays
                # consistent — one source of truth for which patterns need sudo.
                from tools.shell_command import _NEEDS_CONFIRMATION as _sudo_patterns
                cmd_str = args.get("command", "")
                is_sudo_command = any(
                    pat.search(cmd_str) for pat, _ in _sudo_patterns
                    if pat.pattern in (r"\bsudo\b", r"\bsu\s+-")
                )

                confirmation = PendingConfirmation(
                    tool_name=name,
                    arguments=args,
                    reason=result["reason"],
                    command_preview=result["preview"],
                    created_at=time.time(),
                    session_id=session_id,
                    requires_sudo_auth=is_sudo_command,  # sudo commands need extra secret
                )
                # Store immediately — if the LLM's final answer call crashes (e.g.
                # Gemini 500), this pending confirmation must survive so the user
                # can still confirm on the next message.
                self._pending_confirmations[session_id] = confirmation
                captured_confirmation.append(confirmation)
                logger.info(
                    "Dangerous command intercepted: tool=%s session=%s command=%r requires_sudo_auth=%s",
                    name, session_id, result["preview"], is_sudo_command,
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
                        continue
                    yield event

                if captured_confirmation:
                    pending_conf = captured_confirmation[0]
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
                    if last_done_event:
                        last_done_event.next_action = "await_confirmation"
                
                # Persist the conversation BEFORE yielding done so that
                # chat() can close the DB session right after this yield
                # (and before the frontend disconnects + cancels the task).
                full_answer = "".join(answer_parts)
                if full_answer and last_done_event:
                    tool_calls_json = [
                        {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result, "error": tc.error}
                        for tc in last_done_event.tool_calls
                    ]
                    await memory_manager.store(session_id, user_request, full_answer, tool_calls_json)

                if last_done_event:
                    yield last_done_event

                # ✅ Clean exit.
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
                # memory_manager.store() has already been called above (before
                # yielding done) for the normal completion path.  The finally
                # block is intentionally left empty: for mid-stream cancellations
                # last_done_event is None so there is nothing to persist, and
                # attempting an async store here would fail inside the cancelled
                # anyio scope anyway.
                pass

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        if inspect.iscoroutinefunction(tool.execute):
            return await tool.execute(**args)
        else:
            return await asyncio.to_thread(tool.execute, **args)
