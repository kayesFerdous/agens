from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class AppHeader(Widget):
    """Top bar — fixed height 1.
    Left zone:  ◆ Assistant  <session-id>
    Right zone: ↑↓/models  tokens: N  ●
    """

    def __init__(self, session_id: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._session_id = session_id

    def compose(self) -> ComposeResult:
        # Left zone
        yield Static("◆ Agens", classes="header-title")
        # Spacer
        yield Static("", classes="header-spacer")
        # Center zone
        sid = f"session id: {self._session_id}" if self._session_id else ""
        yield Static(sid, classes="header-session", id="header-session")
        # Spacer — pushes right zone to far edge
        yield Static("", classes="header-spacer")
        # Right zone
        yield Static("tokens: 0", classes="header-tokens", id="header-tokens")
        yield Static("  ●", classes="header-status", id="header-status")

    def update_session(self, session_id: str) -> None:
        self._session_id = session_id
        try:
            self.query_one("#header-session", Static).update(
                f"session id: {session_id}" if session_id else ""
            )
        except Exception:
            pass

    def update_model(self, model: str) -> None:
        # model label is no longer in the top bar; kept for compat
        pass

    def update_tokens(self, count: int) -> None:
        try:
            self.query_one("#header-tokens", Static).update(f"tokens: {count:,}")
        except Exception:
            pass

    def set_status_dot(self, active: bool) -> None:
        """Set the status dot — green=active key, dim=no active key."""
        try:
            dot = self.query_one("#header-status", Static)
            dot.update("  ●")
            if active:
                dot.remove_class("status-inactive")
                dot.add_class("status-active")
            else:
                dot.remove_class("status-active")
                dot.add_class("status-inactive")
        except Exception:
            pass
