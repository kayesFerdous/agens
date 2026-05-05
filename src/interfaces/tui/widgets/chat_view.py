from __future__ import annotations

from textual.containers import Vertical, VerticalScroll
from textual.widget import Widget


class ChatView(VerticalScroll):
    """Scrollable chat transcript."""

    DEFAULT_CSS = "ChatView > Vertical { width: 100%; }"

    def compose(self):
        yield Vertical(id="chat-content")

    async def mount_message(self, widget: Widget) -> None:
        await self.query_one("#chat-content", Vertical).mount(widget)
        self.call_after_refresh(self.scroll_end, animate=False)

    async def clear_messages(self) -> None:
        container = self.query_one("#chat-content", Vertical)
        for child in list(container.children):
            await child.remove()
        self.call_after_refresh(self.scroll_home, animate=False)

    def scroll_to_bottom(self) -> None:
        self.call_after_refresh(self.scroll_end, animate=False)
