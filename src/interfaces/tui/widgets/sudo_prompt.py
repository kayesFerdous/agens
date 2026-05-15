"""Secure inline password prompt for sudo commands in the TUI.

Renders a minimal password input that masks characters. The entered
password is returned via an asyncio Future and is never stored, logged,
or sent to the LLM.
"""
from __future__ import annotations

import asyncio

from textual import events
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Input, Static


class SudoPasswordPrompt(Widget):
    """Inline password prompt — enter or escape to resolve."""

    can_focus = True

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._result: asyncio.Future[str | None] | None = None
        self._resolved = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="sudo-prompt-box"):
            yield Static("🔒 Sudo Password", classes="sudo-prompt-title")
            yield Static(
                "Enter your system password to authorize this command.",
                classes="sudo-prompt-hint",
            )
            yield Input(
                placeholder="Password",
                password=True,
                id="sudo-password-input",
                classes="sudo-prompt-input",
            )
            yield Static(
                "[dim]enter[/dim] submit  ·  [dim]esc[/dim] cancel",
                classes="sudo-prompt-keys",
            )

    def on_mount(self) -> None:
        if self._result is None:
            self._result = asyncio.get_running_loop().create_future()
        pw_input = self.query_one("#sudo-password-input", Input)
        pw_input.focus()

    async def wait(self) -> str | None:
        """Block until the user submits or cancels. Returns password or None."""
        if self._result is None:
            self._result = asyncio.get_running_loop().create_future()
        return await self._result

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        value = event.value.strip()
        if value:
            self._resolve(value)
        # Ignore empty submissions — user probably hit Enter by accident.

    def on_key(self, event: events.Key) -> None:
        if event.key == "escape":
            event.stop()
            event.prevent_default()
            self._resolve(None)

    def _resolve(self, value: str | None) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.add_class("resolved")
        if self._result is not None and not self._result.done():
            self._result.set_result(value)
