# llm/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Callable, AsyncIterator, Awaitable
from dataclasses import dataclass, field
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from core.types import StreamEvent, ToolCall, Usage
from services.api_key_manager import APIKeyManager


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

    @property
    @abstractmethod
    def current_key_id(self) -> str:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...
    # @abstractmethod
    # async def generate(
    #     self,
    #     prompt: str,
    #     *,
    #     system: str = "",
    #     temperature: float = 0,
    # ) -> str:
    #     """Return a plain-text completion."""
    #     ...
    #
    # @abstractmethod
    # async def generate_structured(
    #     self,
    #     prompt: str,
    #     *,
    #     system: str = "",
    #     temperature: float = 0,
    #     response_schema: dict[str, Any] | None = None,
    # ) -> str:
    #     """Return a JSON string. Optionally constrained by *response_schema*."""
    #     ...
    #
    # @abstractmethod
    # def generate_stream(
    #     self,
    #     prompt: str,
    #     *,
    #     system: str = "",
    #     temperature: float = 0,
    # ) -> AsyncIterator[str]:
    #     """Yield text chunks as they arrive from the model."""
    #     ...

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
        temperature: float = 0, #INFO: Not using model_name coz, only the web interface will be using the model_name or not streaming the model_name will set differently. Maybe via command
    ) -> str:
        """Run a ReAct loop and return the final text answer.

        The LLM generates function calls; *tool_executor* runs them and
        returns structured dicts. The loop continues until the LLM returns
        a text response or *max_iterations* is reached.
        """
        ...

    @abstractmethod
    def react_stream(
        self,
        user_request: str,
        *,
        system: str = "",
        tool_schemas: list[dict],
        message_history: list[Any] | None = None,
        tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
        max_iterations: int = 10,
        temperature: float = 0,
        model_name: str | None = None,
        streaming: bool = True,
    ) -> AsyncIterator[StreamEvent]:
        """Evented variant of react().

        Yields StreamEvent objects in real time:
          tool_start / tool_end — as tools execute
          token                 — text chunks, or one complete final answer when streaming=False
          done                  — stream complete with usage + tool history
        """
        ...


    async def handle_model_error(
        self,
        db: AsyncSession,
        model: str,
        error: "RateLimitError",  # noqa: F821 — avoid circular import at module level
        api_key_manager: APIKeyManager,
    ) -> None:
        """Set a per-model cooldown and rotate to another key if one is available."""
        ...

    async def ensure_model_key(self, db: AsyncSession, model: str, api_key_manager: APIKeyManager) -> bool:
        """Ensure the current key is available for the given model, swapping if necessary."""
        ...
