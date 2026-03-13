# core/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskStep:
    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    success: bool
    output: str
    step: TaskStep

    @staticmethod
    def ok(step: TaskStep, output: str) -> TaskResult:
        return TaskResult(success=True, output=output, step=step)

    @staticmethod
    def fail(step: TaskStep, output: str) -> TaskResult:
        return TaskResult(success=False, output=output, step=step)


@dataclass
class AgentResponse:
    success: bool
    results: list[TaskResult] = field(default_factory=list)
    error: str | None = None
