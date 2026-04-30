from __future__ import annotations

import asyncio

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.logging import get_logger
from typing import Any, AsyncIterator
from db.repositories.api_key import APIKeyRepository
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import StreamEvent
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager
from llm.llm_exceptions import RateLimitError, LLMUnavailable
from services.api_key_manager import APIKeyManager

logger = get_logger(__name__)


class Agent:
    def __init__(self, registry: ToolRegistry, llm: LLM, config_manager: ConfigManager) -> None:
        self._registry = registry
        self._llm = llm
        self._config_manager = config_manager


    async def run(self, user_request: str, session_id: str, db: AsyncSession, fernet: Fernet) -> str:
        """Non-streaming ReAct loop. Returns the final text answer.

        Uses per-model cooldowns: on RateLimitError, only the failing model is
        marked on cooldown and we switch to another key that can still serve it.
        """
        memory_manager = MemoryManager(db)
        system = build_system_prompt(self._config_manager)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        provider = "gemini"
        api_key_manager = APIKeyManager(repo=APIKeyRepository(db), fernet=fernet)
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
        fernet: Fernet,
        model: str | None = None
    ) -> AsyncIterator[StreamEvent]:
        memory_manager = MemoryManager(db)
        system = build_system_prompt(self._config_manager)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        model_name = None
        if model:
            _, model_name = model.split("/", maxsplit=1)

        # provider = "gemini"  # TODO: derive from model prefix when multi-provider support lands
        api_key_manager = APIKeyManager(repo=APIKeyRepository(db), fernet=fernet)

        answer_parts: list[str] = []
        last_done_event: StreamEvent | None = None
        max_retries = 3

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
                    tool_executor=self._execute_tool,
                    message_history=message_history,
                    model_name=model_name,
                ):
                    if event.type == "token" and event.content:
                        answer_parts.append(event.content)
                    if event.type == "done":
                        last_done_event = event
                    yield event

                # ✅ Clean exit — record usage and reset failure counters.
                await api_key_manager.on_success(self._llm.current_key_id)
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

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        # Execute the tool safely within a thread pool since tools themselves are synchronous
        return await asyncio.to_thread(tool.execute, **args)
