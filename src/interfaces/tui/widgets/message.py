from __future__ import annotations

from rich.markdown import Markdown as RichMarkdown
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Markdown, Static


class UserMessage(Widget):
    def __init__(self, text: str) -> None:
        super().__init__(classes="user-message")
        self.text = text

    def compose(self) -> ComposeResult:
        with Vertical(classes="user-box"):
            yield Static("You", classes="message-label user-label")
            yield Static(self.text)


class AssistantMessage(Widget):
    content = reactive("")

    def __init__(self) -> None:
        super().__init__(classes="assistant-message")
        self._markdown: Markdown | None = None

    def compose(self) -> ComposeResult:
        yield Static("◆ Assistant", classes="message-label")
        yield Static("─" * 80, classes="assistant-rule")
        self._markdown = Markdown("", classes="assistant-markdown")
        yield self._markdown

    def append_text(self, chunk: str) -> None:
        self.content += chunk
        if self._markdown is not None:
            self._markdown.update(self.content)

    def mark_interrupted(self) -> None:
        self.append_text("\n\n_[interrupted]_")


class SystemMessage(Widget):
    def __init__(self, text: str) -> None:
        super().__init__(classes="system-message")
        self.text = text

    def compose(self) -> ComposeResult:
        yield Static(RichMarkdown(self.text))
