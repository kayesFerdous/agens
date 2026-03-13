# planner/planner.py
from __future__ import annotations
import json
import logging
from llm.base import LLM
from core.types import TaskStep
from planner.prompt_builder import build_prompt

logger = logging.getLogger(__name__)


class Planner:
    def __init__(self, llm: LLM, tool_descriptions: list[dict[str, str]]) -> None:
        self._llm = llm
        self._tool_descriptions = tool_descriptions

    def plan(self, user_request: str) -> list[TaskStep]:
        system, prompt = build_prompt(user_request, self._tool_descriptions)
        raw = self._llm.generate(prompt, system=system)
        logger.info("Planner raw output:\n%s", raw)

        steps_data = json.loads(raw)
        if not isinstance(steps_data, list):
            raise ValueError(f"Planner returned non-list: {type(steps_data)}")

        steps: list[TaskStep] = []
        for item in steps_data:
            steps.append(TaskStep(
                tool=item["tool"],
                arguments=item.get("arguments", {}),
            ))
        return steps
