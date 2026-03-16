# core/types.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool invocation recorded during the ReAct loop."""
    tool: str
    arguments: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class AgentResponse:
    success: bool
    answer: str | None = None
    tool_history: list[ToolCall] = field(default_factory=list)
    error: str | None = None
