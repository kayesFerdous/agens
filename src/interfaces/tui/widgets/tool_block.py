from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class ToolBlock(Widget):
    """
    Displays a single tool call inline in chat.
    Shows tool name and args summary. Expandable to show full output.
    """

    expanded: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    ToolBlock {
        height: auto;
        width: 100%;
        background: transparent;
        border: none;
        padding: 0 0 0 2;
        margin: 0;
    }
    ToolBlock Static {
        height: auto;
        width: 100%;
        background: transparent;
    }
    ToolBlock .tool-output {
        background: #111111;
        padding: 0 0 0 4;
        border-left: solid #2a2a2a;
        color: #6b6b6b;
        margin: 0 0 0 2;
    }
    """

    def __init__(self, tool_name: str, args: dict | str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._args = args if isinstance(args, str) else self._fmt_args(args)
        self._output = ""

    def _fmt_args(self, args: dict) -> str:
        parts = []
        for key, value in args.items():
            value_str = str(value)
            if len(value_str) > 40:
                value_str = value_str[:37] + "..."
            parts.append(f"{key}={value_str}")
        return "  ".join(parts[:3])

    def compose(self) -> ComposeResult:
        yield Static(self._make_header(), id="tool-header")
        yield Static("", id="tool-output", classes="tool-output")

    def _make_header(self) -> Text:
        line = Text()
        icon = "└─" if not self.expanded else "├─"
        line.append(f"  {icon} ", style=Style(color="#3f3f3f"))
        line.append(self._tool_name, style=Style(color="#cc785c", bold=True))
        if self._args:
            line.append("  ", style=Style(color="#3f3f3f"))
            line.append(self._args, style=Style(color="#5a5a5a"))
        if self._output:
            hint = "  ▼ click to collapse" if self.expanded else "  ▶ click to expand"
            line.append(hint, style=Style(color="#3f3f3f", italic=True))
        return line

    def set_output(self, output: str) -> None:
        self._output = output
        self.query_one("#tool-header", Static).update(self._make_header())

    def on_click(self) -> None:
        if not self._output:
            return
        self.expanded = not self.expanded
        self.query_one("#tool-header", Static).update(self._make_header())
        out_widget = self.query_one("#tool-output", Static)
        if self.expanded:
            truncated = self._output[:2000]
            if len(self._output) > 2000:
                truncated += "\n... (truncated)"
            out_widget.update(truncated)
        else:
            out_widget.update("")
