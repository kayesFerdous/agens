from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

# AGENS — ANSI Shadow variant (hand-tuned block characters)
_LOGO = """\
██████╗  ██████╗ ███████╗███╗  ██╗███████╗
██╔══██╗██╔════╝ ██╔════╝████╗ ██║██╔════╝
███████║██║  ███╗█████╗  ██╔██╗██║███████╗
██╔══██║██║   ██║██╔══╝  ██║╚████║╚════██║
██║  ██║╚██████╔╝███████╗██║ ╚███║███████║
╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚══╝╚══════╝"""

_TAGLINE = "reason, act, and execute asynchronously"
_HINT = "press any key to begin"


class WelcomeScreen(Widget):
    """Full-screen welcome overlay shown on cold start only.

    Mount it directly on the App (not inside ChatView) so it can sit on top
    of the entire layout.  Call ``dismiss()`` to remove it.
    """

    DEFAULT_CSS = ""  # all rules live in ASSISTANT_CSS

    def compose(self) -> ComposeResult:
        yield Static(_LOGO, id="welcome-logo")
        yield Static(_TAGLINE, id="welcome-tagline")
        yield Static(_HINT, id="welcome-hint")
