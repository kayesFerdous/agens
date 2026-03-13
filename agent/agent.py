# agent/agent.py
from __future__ import annotations
import logging
from core.registry import ToolRegistry
from core.types import AgentResponse, TaskResult, TaskStep
from planner.planner import Planner

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, planner: Planner, registry: ToolRegistry) -> None:
        self._planner = planner
        self._registry = registry

    def run(self, user_request: str) -> AgentResponse:
        logger.info("User request: %s", user_request)

        try:
            steps = self._planner.plan(user_request)
        except Exception as e:
            return AgentResponse(success=False, error=f"Planning failed: {e}")

        logger.info("Plan: %d step(s)", len(steps))
        for i, step in enumerate(steps, 1):
            logger.info("  [%d] %s(%s)", i, step.tool, step.arguments)

        results: list[TaskResult] = []
        for i, step in enumerate(steps, 1):
            logger.info("--- Executing step %d: %s ---", i, step.tool)
            result = self._execute_step(step)
            results.append(result)

            if not result.success:
                logger.error("Step %d failed: %s", i, result.output)
                return AgentResponse(success=False, results=results, error=result.output)

            logger.info("Step %d result: %s", i, result.output[:200])

        logger.info("All %d steps completed successfully.", len(steps))
        return AgentResponse(success=True, results=results)

    def _execute_step(self, step: TaskStep) -> TaskResult:
        try:
            tool = self._registry.get(step.tool)
        except KeyError as e:
            return TaskResult.fail(step, str(e))

        try:
            output = tool.execute(**step.arguments)
            return TaskResult.ok(step, output)
        except Exception as e:
            return TaskResult.fail(step, f"{type(e).__name__}: {e}")
