from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from .tool_block import ToolBlock


class ToolGroup(Widget):
    """
    Container for one or more tool calls in a single agent turn.
    """

    DEFAULT_CSS = """
    ToolGroup {
        height: auto;
        width: 100%;
        background: transparent;
        border: none;
        padding: 0 0 1 0;
        margin: 0;
    }
    ToolGroup .tg-header {
        color: #4b5563;
        padding: 0 2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._blocks: list[ToolBlock] = []

    def compose(self) -> ComposeResult:
        yield Static("", classes="tg-header", id="tg-header")

    async def add_tool(self, tool_name: str, args: dict | str = "") -> ToolBlock:
        block = ToolBlock(tool_name, args)
        self._blocks.append(block)
        await self.mount(block)
        self._update_header()
        return block

    def _update_header(self) -> None:
        count = len(self._blocks)
        plural = "s" if count != 1 else ""
        self.query_one("#tg-header", Static).update(
            f"  ● Running {count} tool{plural}...  (click to expand)"
        )
