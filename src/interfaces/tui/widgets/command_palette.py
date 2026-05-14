from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

COMMANDS = [
    ("/help", "Show all available commands"),
    ("/clear", "Clear the chat history"),
    ("/exit", "Exit the assistant"),
    ("/quit", "Exit the assistant"),
    ("/models", "Select a model interactively"),
    ("/tools", "Select active tool groups"),
    ("/keys", "List registered API keys"),
    ("/addkey", "Add a new API key"),
    ("/tokens", "Show session token count"),
]


class CommandPalette(Widget):
    """
    Inline command suggestion list. Appears above input when user types '/'.
    Disappears when input no longer starts with '/'.
    """

    filter: reactive[str] = reactive("")

    DEFAULT_CSS = """
    CommandPalette {
        height: auto;
        width: 100%;
        background: #0F0D0A;
        border-top: none;
        padding: 0 3;
        display: none;
    }
    CommandPalette.visible {
        display: block;
    }
    CommandPalette Static {
        height: auto;
        width: 100%;
        background: transparent;
        padding: 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="palette-content")

    def watch_filter(self, value: str) -> None:
        if not value.startswith("/"):
            self.remove_class("visible")
            return

        matches = [(cmd, desc) for cmd, desc in COMMANDS if cmd.startswith(value)]

        if not matches:
            self.remove_class("visible")
            return

        lines = Text()
        for i, (cmd, desc) in enumerate(matches):
            if i > 0:
                lines.append("\n")
            lines.append(cmd, style=Style(color="#7B6EAA", bold=True))
            lines.append("  ")
            lines.append(desc, style=Style(color="#8C877E"))

        self.query_one("#palette-content", Static).update(lines)
        self.add_class("visible")

    def hide(self) -> None:
        self.remove_class("visible")
        self.filter = ""
