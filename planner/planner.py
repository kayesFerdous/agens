# planner/planner.py
from __future__ import annotations
import json
import logging
from pathlib import Path
from llm.base import LLM
from core.types import TaskStep
from planner.prompt_builder import build_prompt
from config.workspace import WORKSPACE_ROOT
from config.logging import get_logger, setup_logging

setup_logging()

logger = get_logger(__name__)

# Argument keys that are expected to hold filesystem paths
_PATH_ARGS = {"path", "directory", "file", "dest", "source", "target"}


class Planner:
    def __init__(
        self,
        llm: LLM,
        tool_descriptions: list[dict[str, str]],
        known_tool_names: set[str],
    ) -> None:
        self._llm = llm
        self._tool_descriptions = tool_descriptions
        self._known_tool_names = known_tool_names

    def plan(self, user_request: str) -> list[TaskStep]:
        system, prompt = build_prompt(user_request, self._tool_descriptions)
        raw = self._llm.generate(prompt, system=system, temperature=0)
        logger.info("Planner raw output:\n%s", raw)

        steps = self._parse(raw)
        error = self._validate(steps)

        if error:
            logger.warning("Plan validation failed: %s — retrying once.", error)
            correction_prompt = (
                f"Original request: {user_request}\n\n"
                f"Your previous plan had this error: {error}\n\n"
                "Produce a corrected JSON array following all the rules."
            )
            raw2 = self._llm.generate(correction_prompt, system=system, temperature=0)
            logger.info("Planner retry output:\n%s", raw2)
            steps = self._parse(raw2)
            error2 = self._validate(steps)
            if error2:
                raise ValueError(f"Plan invalid after retry: {error2}")

        return steps

    # ------------------------------------------------------------------
    def _parse(self, raw: str) -> list[TaskStep]:
        steps_data = json.loads(raw)
        if not isinstance(steps_data, list):
            raise ValueError(f"Planner returned non-list: {type(steps_data)}")
        return [
            TaskStep(
                tool=item["tool"],
                arguments=item.get("arguments", {}),
                output_key=item.get("output_key"),
                depends_on=item.get("depends_on"),
            )
            for item in steps_data
        ]

    def _validate(self, steps: list[TaskStep]) -> str | None:
        """Return an error description string, or None if valid."""
        declared_keys: set[str] = set()

        for i, step in enumerate(steps, 1):
            if step.tool not in self._known_tool_names:
                known = ", ".join(sorted(self._known_tool_names))
                return (
                    f"Step {i}: unknown tool '{step.tool}'. "
                    f"Valid tools: {known}"
                )
            for key, val in step.arguments.items():
                if key in _PATH_ARGS and isinstance(val, str):
                    try:
                        Path(val).resolve().relative_to(WORKSPACE_ROOT)
                    except ValueError:
                        return (
                            f"Step {i} ({step.tool}): path argument '{key}={val}' "
                            f"is outside workspace root '{WORKSPACE_ROOT}'."
                        )
            if step.depends_on:
                for arg_name, ctx_key in step.depends_on.items():
                    if ctx_key not in declared_keys:
                        return (
                            f"Step {i} ({step.tool}): depends_on references "
                            f"'{ctx_key}' which is not an output_key of any earlier step."
                        )
            if step.output_key:
                declared_keys.add(step.output_key)

        return None

