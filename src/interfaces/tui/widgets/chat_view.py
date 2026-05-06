from __future__ import annotations

from textual.widget import Widget


class ChatView(Widget):
    """
    The main chat canvas.

    This is not a panel, card, or bordered container. It uses Widget scrolling
    via CSS overflow because the low-level Textual scroll base renders a
    diagnostic panel unless a subclass implements its own rendering.
    """

    async def add_user(self, text: str) -> None:
        from .messages import UserBlock

        await self._add_widget(UserBlock(text))

    async def add_assistant(self) -> "AssistantBlock":
        from .messages import AssistantBlock

        widget = AssistantBlock()
        await self._add_widget(widget)
        return widget

    async def add_system(self, text: str) -> None:
        from .messages import SystemLine

        await self._add_widget(SystemLine(text))

    async def add_spinner(self) -> "LiveSpinner":
        from .spinner import LiveSpinner

        widget = LiveSpinner()
        await self._add_widget(widget)
        return widget

    async def clear_all(self) -> None:
        for child in list(self.children):
            await child.remove()
        self.scroll_home(animate=False)

    async def _add_widget(self, widget: Widget) -> None:
        await self.mount(widget)
        self.scroll_end(animate=False)
