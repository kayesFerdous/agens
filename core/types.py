# core/types.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any

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
