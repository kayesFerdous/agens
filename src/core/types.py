# core/types.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Literal, TYPE_CHECKING

logger = logging.getLogger(__name__)


@dataclass
class Usage:
    """Provider-agnostic token usage accumulator.

    Each provider is responsible for extracting counts from its own
    response type and calling ``record()`` with plain ints.
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def record(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens

    def log(self, logger: logging.Logger, *, model: str = "", context: str = "") -> None:
        logger.info(
            "token_usage model=%s context=%s prompt=%d completion=%d total=%d",
            model,
            context,
            self.prompt_tokens,
            self.completion_tokens,
            self.total_tokens,
        )


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
    usage: Usage | None = None


@dataclass
class StreamEvent:
    """A single event yielded during a streaming ReAct loop.

    Event types:
        tool_start — a tool is about to be executed
        tool_end   — a tool finished (with result or error)
        token      — a chunk of the final text answer
        status     — a non-error lifecycle update for the UI
        error      — an unrecoverable error occurred
        done       — the stream is complete (carries usage + tool history)
    """
    type: Literal[
        "tool_start", "tool_end", "token", "status", "error", "done", "model",
    ]

    # token events
    content: str | None = None

    # status events
    message: str | None = None

    # tool events
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    # done event
    usage: Usage | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    # model event
    active_model: str | None = None
