# agent/agent.py
from __future__ import annotations
from config.logging import get_logger, setup_logging
from typing import Any
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import AgentResponse
from planner.prompt_builder import build_system_prompt

setup_logging()

logger = get_logger(__name__)


class Agent:
    def __init__(self, registry: ToolRegistry, llm: LLM) -> None:
        self._registry = registry
        self._llm = llm

    def run(self, user_request: str) -> AgentResponse:
        logger.info("User request: %s", user_request)

        system = build_system_prompt()
        tool_schemas = self._registry.tool_schemas()

        try:
            result = self._llm.react(
                user_request,
                system=system,
                tool_schemas=tool_schemas,
                tool_executor=self._execute_tool,
            )
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
            tool_history=result.tool_calls, # pyright: ignore
        )

    def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        return tool.execute(**args)
