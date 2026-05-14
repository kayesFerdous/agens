from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


class NoAPIKeysOnboarding(Widget):
    can_focus = True

    class AddKey(Message):
        pass

    class Dismiss(Message):
        pass

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected = "yes"

    def compose(self) -> ComposeResult:
        with Vertical(classes="no-keys-box"):
            yield Static("API key required", classes="no-keys-title")
            yield Static(
                "Add an active key to start chatting. Commands remain available.",
                classes="no-keys-copy",
            )
            yield Static("", classes="no-keys-option yes")
            yield Static("", classes="no-keys-option no")
            yield Static(
                "Use up/down, y/n, or Enter.",
                classes="no-keys-shortcuts",
            )

    def on_mount(self) -> None:
        self._sync_selection()
        self.focus()

    def handle_prompt_key(self, event: events.Key) -> bool:
        key = event.key.lower()
        if key in {"down", "tab"}:
            self._selected = "no"
        elif key in {"up", "shift+tab"}:
            self._selected = "yes"
        elif key == "y":
            self._selected = "yes"
            self._choose()
        elif key == "n":
            self._selected = "no"
            self._choose()
        elif key == "enter":
            self._choose()
        else:
            return False

        self._sync_selection()
        event.stop()
        event.prevent_default()
        return True

    def on_key(self, event: events.Key) -> None:
        self.handle_prompt_key(event)

    def _choose(self) -> None:
        if self._selected == "yes":
            self.post_message(self.AddKey())
        else:
            self.post_message(self.Dismiss())

    def _sync_selection(self) -> None:
        yes = self.query_one(".yes", Static)
        no = self.query_one(".no", Static)
        yes.update(self._option_label("yes", "Y", "Add API Key"))
        no.update(self._option_label("no", "N", "Not now"))
        yes.set_class(self._selected == "yes", "selected")
        no.set_class(self._selected == "no", "selected")

    def _option_label(self, value: str, key: str, label: str) -> str:
        selected = self._selected == value
        prefix = ">" if selected else " "
        key_style = "bold #A99DD1" if selected else "#56524C"
        label_style = "bold #F5F0E8" if selected else "#8C877E"
        return f"[#7B6EAA]{prefix}[/] [{key_style}]{key}[/]  [{label_style}]{label}[/]"
