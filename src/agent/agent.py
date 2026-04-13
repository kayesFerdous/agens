from __future__ import annotations

import asyncio

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio.session import AsyncSession
from config.settings import settings
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
from db.database import async_session

logger = get_logger(__name__)


class Agent:
    def __init__(self, registry: ToolRegistry, llm: LLM, config_manager: ConfigManager) -> None:
        self._registry = registry
        self._llm = llm
        self._config_manager = config_manager


    async def run_stream(self, user_request: str, session_id: str, db: AsyncSession) -> AsyncIterator[StreamEvent]:
        memory_manager = MemoryManager(db)
        config = self._config_manager.load_config()
        system = build_system_prompt(config)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        answer_parts: list[str] = []
        last_done_event: StreamEvent | None = None
        max_key_rotations = 3

        for attempt in range(max_key_rotations):
            answer_parts.clear()
            last_done_event = None
            rotated = False

            try:
                async for event in self._llm.react_stream(
                    user_request,
                    system=system,
                    tool_schemas=tool_schemas,
                    tool_executor=self._execute_tool,
                    message_history=message_history,
                ):
                    if event.type == "token" and event.content:
                        answer_parts.append(event.content)
                    if event.type == "done":
                        last_done_event = event
                    yield event
                break  # clean exit, no rotation needed

            except RateLimitError as e:
                logger.warning("Stream rate limit on attempt %d: key=%s daily=%s", attempt, e.key_id, e.is_daily)

                fernet = Fernet(key=settings.FERNET_SECRET)
                async with async_session() as session:
                    repo = APIKeyRepository(session)
                    keys = APIKeyManager(repo, fernet=fernet)
                    try:
                        await keys.on_rate_limit(
                            e.key_id, retry_after=e.retry_after, is_daily=e.is_daily
                        )
                        await self._llm.rotate_key(keys)
                        yield StreamEvent(
                            type="status",
                            message="API key rotated. Retrying the request.",
                        )
                        rotated = True
                    except RuntimeError:
                        yield StreamEvent(type="error", error="All API keys are exhausted.")
                        return

                if not rotated:
                    yield StreamEvent(type="error", error="Rate limit hit, could not rotate key.")
                    return
            except LLMUnavailable as e:
                logger.warning(e)

                fernet = Fernet(key=settings.FERNET_SECRET)
                async with async_session() as session:
                    repo = APIKeyRepository(session)
                    keys = APIKeyManager(repo, fernet=fernet)
                    try:
                        await self._llm.rotate_key(keys)
                    except RuntimeError:
                        yield StreamEvent(type="error", error="All API keys are exhausted.")
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
