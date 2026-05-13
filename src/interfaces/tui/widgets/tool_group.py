from __future__ import annotations

from rich.style import Style
from rich.text import Text
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
        padding: 0;
        margin: 1 0 0 0;
    }
    ToolGroup .tg-header {
        color: #56524C;
        padding: 0 3;
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
        self._render_header(done=False)

    def mark_done(self) -> None:
        self._render_header(done=True)

    def _render_header(self, done: bool = False) -> None:
        count = len(self._blocks)
        plural = "s" if count != 1 else ""
        if done:
            text = Text(
                f"  ✓ {count} tool{plural} complete",
                style=Style(color="#56524C"),
            )
        else:
            text = Text(
                f"  ● {count} tool{plural} running",
                style=Style(color="#C97C4A"),
            )
        self.query_one("#tg-header", Static).update(text)
