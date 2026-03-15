# llm/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Any


class LLM(ABC):
    """Abstract base for all LLM backends.

    Subclasses must implement three generation modes:
        generate          – plain text completion
        generate_structured – JSON / schema-constrained output
        generate_stream     – token-by-token streaming
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> str:
        """Return a plain-text completion."""
        ...

    @abstractmethod
    def generate_structured(
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
    def generate_stream(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float = 0,
    ) -> Iterator[str]:
        """Yield text chunks as they arrive from the model."""
        ...
