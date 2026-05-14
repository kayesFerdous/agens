from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

_FULL_LOGO = """\
 █████╗  ██████╗ ███████╗███╗   ██╗███████╗
██╔══██╗██╔════╝ ██╔════╝████╗  ██║██╔════╝
███████║██║  ███╗█████╗  ██╔██╗ ██║███████╗
██╔══██║██║   ██║██╔══╝  ██║╚██╗██║╚════██║
██║  ██║╚██████╔╝███████╗██║ ╚████║███████║
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝
"""
_COMPACT_LOGO = "AGENS"

_TAGLINE = "reason, act, and execute asynchronously"
_HINT = "send a message to begin"


class WelcomeScreen(Widget):
    """Bounded full-screen welcome overlay shown on cold start only."""

    DEFAULT_CSS = ""  # all rules live in ASSISTANT_CSS

    def compose(self) -> ComposeResult:
        yield Static("", id="welcome-content")

    def on_mount(self) -> None:
        self._refresh_content()

    def on_resize(self, _: events.Resize) -> None:
        self._refresh_content()

    def _refresh_content(self) -> None:
        try:
            self.query_one("#welcome-content", Static).update(self._build_content())
        except Exception:
            pass

    def _build_content(self) -> str:
        # Textual will add scrollbars if child content exceeds the viewport, so
        # every rendered line and spacer is capped from the live terminal size.
        width = max(1, self.app.size.width)
        height = max(1, self.app.size.height)

        logo = _FULL_LOGO.splitlines() if width >= 46 and height >= 10 else [_COMPACT_LOGO]
        lines = [self._fit_line(line, width) for line in logo]

        if height >= len(lines) + 3:
            lines.extend(["", self._fit_line(_TAGLINE, width)])
        if height >= len(lines) + 2:
            lines.extend(["", self._fit_line(_HINT, width)])

        visible = lines[:height]
        top_padding = max(0, (height - len(visible)) // 2)
        return "\n" * top_padding + "\n".join(visible)

    def _fit_line(self, line: str, width: int) -> str:
        if len(line) <= width:
            return line.center(width)
        if width <= 1:
            return line[:width]
        return line[:width]
