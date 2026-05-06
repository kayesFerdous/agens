from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static


class AppHeader(Widget):
    def compose(self) -> ComposeResult:
        yield Static("◆ Assistant", classes="header-title")
        yield Static("", classes="header-model", id="header-model")
        yield Static("tokens: 0", classes="header-tokens", id="header-tokens")

    def update_model(self, model: str) -> None:
        self.query_one("#header-model", Static).update(model)

    def update_tokens(self, count: int) -> None:
        self.query_one("#header-tokens", Static).update(f"tokens: {count}")
