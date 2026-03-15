# agent/agent.py
from __future__ import annotations
from config.logging import get_logger, setup_logging
from typing import Any
from llm.base import LLM
from core.registry import ToolRegistry
from core.types import AgentResponse, TaskResult, TaskStep
from planner.planner import Planner

setup_logging()

logger = get_logger(__name__)

_SYNTHESIS_SYSTEM = (
    "You are a helpful assistant. Given the user's original request and the "
    "results from the tools that were executed, produce a single, clear, "
    "natural-language answer. Be concise and focus on directly answering "
    "the user's question."
)


class Agent:
    def __init__(self, planner: Planner, registry: ToolRegistry, llm: LLM) -> None:
        self._planner = planner
        self._registry = registry
        self._llm = llm

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
        context: dict[str, str] = {}

        for i, step in enumerate(steps, 1):
            logger.info("--- Executing step %d: %s ---", i, step.tool)

            if step.depends_on:
                for arg_name, ctx_key in step.depends_on.items():
                    if ctx_key not in context:
                        err = f"Step {i} ({step.tool}): depends_on key '{ctx_key}' not in context"
                        logger.error(err)
                        return AgentResponse(success=False, results=results, error=err)
                    step.arguments[arg_name] = context[ctx_key]

            result = self._execute_step(step)
            results.append(result)

            if not result.success:
                logger.error("Step %d failed: %s", i, result.output)
                return AgentResponse(success=False, results=results, error=result.output)

            if step.output_key:
                context[step.output_key] = result.output
                logger.info("Stored context[%s] = %s", step.output_key, result.output[:120])

            logger.info("Step %d result: %s", i, result.output[:200])

        logger.info("All %d steps completed. Synthesizing answer.", len(steps))
        answer = self._synthesize(user_request, results)
        return AgentResponse(success=True, results=results, answer=answer)

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

    def _synthesize(self, user_request: str, results: list[TaskResult]) -> str:
        steps_summary = "\n\n".join(
            f"Tool: {r.step.tool}\nArguments: {r.step.arguments}\nOutput:\n{r.output}"
            for r in results
        )
        prompt = (
            f"User request: {user_request}\n\n"
            f"Tool results:\n{steps_summary}\n\n"
            "Provide a clear, natural-language answer to the user's request based on the above."
        )
        try:
            return self._llm.generate(prompt, system=_SYNTHESIS_SYSTEM, temperature=0.5)
        except Exception as e:
            logger.warning("Synthesis LLM call failed: %s", e)
            return "\n".join(r.output for r in results)
