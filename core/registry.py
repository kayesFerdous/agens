# core/registry.py
from core.tool_interface import Tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Unknown tool: '{name}'. Available: {list(self._tools)}")
        return tool

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def tool_descriptions(self) -> list[dict[str, str]]:
        return [{"name": t.name} for t in self._tools.values()]
