from __future__ import annotations

from sqlalchemy.ext.asyncio.session import AsyncSession
from config.logging import get_logger, setup_logging
from typing import Any
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import AgentResponse
from config.config_manager import ConfigManager
from planner.prompt_builder import build_system_prompt
from memory.manager import MemoryManager

setup_logging()

logger = get_logger(__name__)


class Agent:
    def __init__(self, registry: ToolRegistry, llm: LLM, config_manager: ConfigManager) -> None:
        self._registry = registry
        self._llm = llm
        self._config_manager = config_manager

    async def run(self, user_request: str, session_id: str, db: AsyncSession) -> AgentResponse:
        memory_manager = MemoryManager(db, session_id)
        logger.info("User request: %s", user_request)

        config = self._config_manager.load_config()
        system = build_system_prompt(config)
        tool_schemas = self._registry.tool_schemas()
        message_history = await memory_manager.get_history_for_gemini()

        try:
            result = self._llm.react(
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
            await memory_manager.store(user_request, result.answer, tool_calls_json)

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
        )

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        return tool.execute(**args)
