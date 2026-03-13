# llm/base.py
from __future__ import annotations
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def generate(self, prompt: str, system: str = "") -> str:
        """Send prompt to the model and return raw text response."""
        ...
