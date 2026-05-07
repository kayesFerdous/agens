from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Static


_ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@dataclass(frozen=True)
class ConfirmationRequest:
    title: str
    warning: str
    command: str
    yes_label: str = "Yes"
    no_label: str = "No"


class InlineConfirmation(Widget):
    """Compact inline confirmation control for chat-stream decisions."""

    can_focus = True

    def __init__(self, request: ConfirmationRequest, **kwargs) -> None:
        super().__init__(**kwargs)
        self.request = request
        self._selected = "no"
        self._resolved = False
        self._result: asyncio.Future[bool] | None = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirm-box"):
            yield Static(self.request.title, classes="confirm-title")
            yield Static(self._clean_command(self.request.command), classes="confirm-command", markup=False)
            yield Static(self.request.warning, classes="confirm-warning")
            with Horizontal(classes="confirm-actions"):
                yield Button(self.request.yes_label, classes="confirm-yes", compact=True)
                yield Button(self.request.no_label, classes="confirm-no", compact=True)

    def on_mount(self) -> None:
        if self._result is None:
            self._result = asyncio.get_running_loop().create_future()
        self._sync_selection()
        self.focus()

    async def wait(self) -> bool:
        if self._result is None:
            self._result = asyncio.get_running_loop().create_future()
        return await self._result

    def handle_key(self, event: events.Key) -> bool:
        key = event.key.lower()
        if key in {"left", "shift+tab"}:
            self._toggle_selection()
        elif key in {"right", "tab"}:
            self._toggle_selection()
        elif key == "enter":
            self.resolve(self._selected == "yes")
        elif key == "escape":
            self.resolve(False)
        elif key == "y":
            self._selected = "yes"
            self.resolve(True)
        elif key == "n":
            self._selected = "no"
            self.resolve(False)
        else:
            return False

        event.stop()
        event.prevent_default()
        return True

    def on_key(self, event: events.Key) -> None:
        self.handle_key(event)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.has_class("confirm-yes"):
            self._selected = "yes"
            self.resolve(True)
        elif event.button.has_class("confirm-no"):
            self._selected = "no"
            self.resolve(False)

    def resolve(self, confirmed: bool) -> None:
        if self._resolved:
            return
        self._resolved = True
        self._selected = "yes" if confirmed else "no"
        self._sync_selection()
        self.add_class("resolved")
        self.query_one(".confirm-actions", Horizontal).display = False
        status = "approved" if confirmed else "cancelled"
        self.query_one(".confirm-warning", Static).update(status)
        if self._result is not None and not self._result.done():
            self._result.set_result(confirmed)

    def _toggle_selection(self) -> None:
        if self._resolved:
            return
        self._selected = "yes" if self._selected == "no" else "no"
        self._sync_selection()

    def _sync_selection(self) -> None:
        yes = self.query_one(".confirm-yes", Button)
        no = self.query_one(".confirm-no", Button)
        yes.set_class(self._selected == "yes", "selected")
        no.set_class(self._selected == "no", "selected")
        if not self._resolved:
            (yes if self._selected == "yes" else no).focus()

    @staticmethod
    def _clean_command(command: str) -> str:
        cleaned = _ANSI_RE.sub("", command or "").strip()
        return cleaned or "(empty command)"
