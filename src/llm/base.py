# llm/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, AsyncIterator, Awaitable
from dataclasses import dataclass, field
from typing import Any
from core.types import StreamEvent, ToolCall, Usage


@dataclass
class ReactResult:
    """Result of a ReAct loop: final answer + history of tool calls."""
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)


class LLM(ABC):
    """Abstract base for all LLM backends.

    Subclasses must implement four generation modes:
        generate            – plain text completion
        generate_structured – JSON / schema-constrained output
        generate_stream     – token-by-token streaming
        react               – ReAct loop with function calling
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> str:
        """Return a plain-text completion."""
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        """Return a JSON string. Optionally constrained by *response_schema*."""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive from the model."""
        ...

    @abstractmethod
    async def react(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 10,
        temperature: float = 0,
    ) -> ReactResult:
        """Run a ReAct loop using function calling.

        The LLM generates function calls; *tool_executor* runs them and
        returns structured dicts. The loop continues until the LLM returns
        a text response or *max_iterations* is reached.
        """
        ...

    @abstractmethod
    async def react_stream(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 10,
        temperature: float = 0,
    ) -> AsyncIterator[StreamEvent]:
        """Streaming variant of react().

        Yields StreamEvent objects in real time:
          tool_start / tool_end — as tools execute
          token                 — text chunks of the final answer
          done                  — stream complete with usage + tool history
        """
        ...
