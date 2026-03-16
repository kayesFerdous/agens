# core/tool_interface.py
from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """Return a JSON Schema dict describing this tool's arguments."""
        ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict:
        """Execute the tool and return a structured result dict."""
        ...
