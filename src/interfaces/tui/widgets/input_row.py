from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Static


class InputRow(Widget):
    def compose(self) -> ComposeResult:
        yield Static("─" * 400, classes="input-top-rule")
        with Horizontal(classes="input-line"):
            yield Static(">", classes="prompt-char")
            yield Input(placeholder="", id="main-input")
        yield Static("─" * 400, classes="input-bottom-rule")

    def on_mount(self) -> None:
        self.focus_input()

    def focus_input(self) -> None:
        try:
            self.query_one("#main-input", Input).focus()
        except Exception:
            pass

    def clear_input(self) -> None:
        try:
            self.query_one("#main-input", Input).value = ""
        except Exception:
            pass

    def get_value(self) -> str:
        try:
            return self.query_one("#main-input", Input).value
        except Exception:
            return ""

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        try:
            palette = self.app.query_one("#command-palette")
            if value.startswith("/"):
                palette.filter = value
            else:
                palette.hide()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        try:
            self.app.query_one("#command-palette").hide()
        except Exception:
            pass
        text = event.value.strip()
        if text:
            self.app.handle_submit(text)
        self.clear_input()
