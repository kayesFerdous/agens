from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio.session import AsyncSession
from config.logging import get_logger
from typing import Any, AsyncIterator
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import AgentResponse, StreamEvent
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager

logger = get_logger(__name__)


class Agent:
    def __init__(self, registry: ToolRegistry, llm: LLM, config_manager: ConfigManager) -> None:
        self._registry = registry
        self._llm = llm
        self._config_manager = config_manager

    async def run(self, user_request: str, session_id: str, db: AsyncSession) -> AgentResponse:
        memory_manager = MemoryManager(db)
        logger.info("User request: %s", user_request)

        config = self._config_manager.load_config()
        system = build_system_prompt(config)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        try:
            result = await self._llm.react(
                user_request,
                system=system,
                tool_schemas=tool_schemas,
                tool_executor=self._execute_tool,
                message_history=message_history
            )

            tool_calls_json = [
                {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result, "error": tc.error}
                for tc in result.tool_calls
            ]
            await memory_manager.store(session_id, user_request, result.answer, tool_calls_json)

        except Exception as e:
            logger.error("ReAct loop failed: %s", e)
            return AgentResponse(success=False, error=str(e))

        logger.info(
            "Completed: %d tool call(s), answer length: %d",
            len(result.tool_calls),
            len(result.answer),
        )
        return AgentResponse(
            success=True,
            answer=result.answer,
            tool_history=result.tool_calls,
            usage=result.usage,
        )

    async def run_stream(self, user_request: str, session_id: str, db: AsyncSession) -> AsyncIterator[StreamEvent]:
        """Streaming variant of run(). Yields StreamEvent objects natively in async."""
        memory_manager = MemoryManager(db)
        logger.info("User request (stream): %s", user_request)

        config = self._config_manager.load_config()
        system = build_system_prompt(config)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini(session_id)

        # Collect token text so we can store the full answer in memory
        answer_parts: list[str] = []
        last_done_event: StreamEvent | None = None

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

        except Exception as e:
            logger.error("Streaming ReAct loop failed: %s", e)
            yield StreamEvent(type="error", error=str(e))

        finally:
            # Store conversation in memory after streaming completes
            full_answer = "".join(answer_parts)
            if full_answer and last_done_event:
                tool_calls_json = [
                    {"tool": tc.tool, "arguments": tc.arguments, "result": tc.result, "error": tc.error}
                    for tc in last_done_event.tool_calls
                ]
                await memory_manager.store(session_id, user_request, full_answer, tool_calls_json)
                logger.info("Stream complete: %d tool call(s), answer length: %d",
                            len(last_done_event.tool_calls), len(full_answer))

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        # Execute the tool safely within a thread pool since tools themselves are synchronous
        return await asyncio.to_thread(tool.execute, **args)
