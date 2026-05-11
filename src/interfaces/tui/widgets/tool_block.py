from __future__ import annotations

import json

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class ToolBlock(Widget):
    """Discrete enclosed tool trace block with collapsible output."""

    expanded: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    ToolBlock {
        height: auto;
        width: 100%;
        background: #1A1713;
        border-left: wide #7B6EAA;
        padding: 1 1 1 2;
        margin: 1 0 0 0;
    }
    ToolBlock Static {
        height: auto;
        width: 100%;
        background: transparent;
        padding: 0;
    }
    """

    def __init__(self, tool_name: str, args: dict | str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._tool_name = tool_name
        self._args = args if isinstance(args, str) else self._summarize_args(args)
        self._output = ""
        self._output_summary = ""

    def _summarize_args(self, args: dict) -> str:
        if not args:
            return ""

        parts = []
        for value in args.values():
            value_str = str(value).replace("\n", " ")
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            parts.append(value_str)
        return "  ".join(parts[:2])

    def _summarize_output(self, raw: str) -> str:
        raw = raw.strip()
        if not raw:
            return "no output"

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            data = None

        if isinstance(data, dict):
            priority_keys = [
                "stdout",
                "output",
                "result",
                "content",
                "error",
                "stderr",
                "exit_code",
                "status",
                "message",
            ]
            parts = []
            for key in priority_keys:
                if key not in data:
                    continue
                value = str(data[key]).strip().replace("\n", " ")
                if value and value not in ("false", "null", "None"):
                    if len(value) > 60:
                        value = value[:57] + "..."
                    parts.append(f"{key}: {value}")
                if len(parts) >= 3:
                    break
            if parts:
                return "  .  ".join(parts)

        first_line = raw.split("\n")[0].strip()
        if len(first_line) > 80:
            first_line = first_line[:77] + "..."
        return first_line if first_line else raw[:80]

    def compose(self) -> ComposeResult:
        yield Static(self._render_line(), id="tool-line")
        yield Static("", id="tool-detail")

    def on_mount(self) -> None:
        self.query_one("#tool-detail", Static).display = False

    def _render_line(self) -> Text:
        text = Text()
        if self._output:
            text.append("✓ ", style=Style(color="#4a7c59"))
        else:
            text.append("● ", style=Style(color="#C97C4A"))

        # Tool name in accent-mid violet
        text.append(self._tool_name, style=Style(color="#A99DD1", bold=True))
        if self._args:
            text.append("  ", style=Style(color="#28251F"))
            # Args in muted text
            text.append(self._args, style=Style(color="#8C877E"))
        if self._output:
            text.append("  ▼" if self.expanded else "  ▶", style=Style(color="#56524C"))
        return text

    def _render_detail(self) -> Text:
        if not self.expanded or not self._output_summary:
            return Text("")

        text = Text()
        # Tool execution result in warm copper
        text.append(self._output_summary, style=Style(color="#C97C4A", italic=True))
        return text

    def set_output(self, output: str) -> None:
        self._output = output
        self._output_summary = self._summarize_output(output)
        self.query_one("#tool-line", Static).update(self._render_line())
        detail = self.query_one("#tool-detail", Static)
        detail.update(self._render_detail())
        detail.display = self.expanded and bool(self._output_summary)

    def on_click(self) -> None:
        if not self._output:
            return

        self.expanded = not self.expanded
        self.query_one("#tool-line", Static).update(self._render_line())
        detail = self.query_one("#tool-detail", Static)
        detail.update(self._render_detail())
        detail.display = self.expanded and bool(self._output_summary)
