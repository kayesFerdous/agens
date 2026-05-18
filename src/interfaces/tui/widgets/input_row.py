from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Static


class InputRow(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._locked = False

    def compose(self) -> ComposeResult:
        yield Static("─" * 400, classes="input-top-rule")
        with Horizontal(classes="input-line"):
            yield Static(">", classes="prompt-char")
            yield Static("Auto ✦", id="model-button", classes="model-button")
            yield Input(placeholder="", id="main-input")
        yield Static("─" * 400, classes="input-bottom-rule")

    def on_mount(self) -> None:
        self.focus_input()

    def focus_input(self) -> None:
        if self._locked:
            return
        try:
            self.query_one("#main-input", Input).focus()
        except Exception:
            pass

    def set_locked(self, locked: bool) -> None:
        self._locked = locked
        try:
            input_widget = self.query_one("#main-input", Input)
            input_widget.disabled = locked
            self.set_class(locked, "locked")
            if locked:
                self.app.query_one("#command-palette").hide()
            else:
                input_widget.focus()
        except Exception:
            pass

    def set_model_label(self, label: str) -> None:
        try:
            self.query_one("#model-button", Static).update(label)
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
        if self._locked:
            event.stop()
            return
        value = event.value
        try:
            palette = self.app.query_one("#command-palette")
            if value.startswith("/"):
                palette.filter = value
            else:
                palette.hide()
        except Exception:
            pass

    def on_click(self, event: events.Click) -> None:
        widget = getattr(event, "widget", None)
        if getattr(widget, "id", None) != "model-button" or self._locked:
            return
        event.stop()
        try:
            self.app.show_model_selector()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        if self._locked:
            return
        try:
            self.app.query_one("#command-palette").hide()
        except Exception:
            pass
        text = event.value.strip()
        if text:
            self.app.handle_submit(text)
        self.clear_input()
