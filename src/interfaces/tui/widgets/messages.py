from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.containers import Vertical
from textual.widgets import Markdown, Static


class UserBlock(Widget):
    """User message: subtle background, left orange bar, no label."""

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(self._text)


class AssistantBlock(Widget):
    """Assistant message: borderless markdown directly on the dark canvas."""

    content: reactive[str] = reactive("", layout=True)

    def compose(self) -> ComposeResult:
        yield Markdown("", id="md-content")

    def append_chunk(self, chunk: str) -> None:
        self.content += chunk

    def mark_interrupted(self) -> None:
        self.append_chunk("\n\n*[interrupted]*")

    def watch_content(self, value: str) -> None:
        try:
            self.query_one("#md-content", Markdown).update(value)
        except Exception:
            pass


class SystemLine(Widget):
    """Muted system message, rendered as terminal output."""

    def __init__(self, text: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._text = text

    def compose(self) -> ComposeResult:
        yield Static(self._text)


class CommandResultBlock(Widget):
    """Compact terminal-native command result."""

    def __init__(
        self,
        *,
        command: str,
        output: str,
        exit_code: object,
        failed: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._command = command
        self._output = output
        self._exit_code = exit_code
        self._failed = failed

    def compose(self) -> ComposeResult:
        title = "Command failed." if self._failed else "Command executed."
        with Vertical(classes="command-result-box"):
            yield Static(title, classes="command-result-title")
            yield Static(f"$ {self._command}", classes="command-result-command", markup=False)
            yield Static(f"exit {self._exit_code}", classes="command-result-exit")
            yield Static(self._output, classes="command-result-output", markup=False)
