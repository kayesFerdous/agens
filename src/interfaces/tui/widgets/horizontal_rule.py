from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.widget import Widget


class HorizontalRule(Widget):
    """Single-line terminal separator, the only visible structural element."""

    def render(self) -> Text:
        width = self.app.console.width
        return Text("─" * width, style=Style(color="#28251F"))
