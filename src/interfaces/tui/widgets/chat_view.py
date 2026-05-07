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

    async def add_confirmation(self, request: "ConfirmationRequest") -> "InlineConfirmation":
        from .inline_confirmation import InlineConfirmation

        widget = InlineConfirmation(request)
        await self._add_widget(widget)
        return widget

    async def add_command_result(
        self,
        *,
        command: str,
        output: str,
        exit_code: object,
        failed: bool = False,
    ) -> "CommandResultBlock":
        from .messages import CommandResultBlock

        widget = CommandResultBlock(
            command=command,
            output=output,
            exit_code=exit_code,
            failed=failed,
        )
        await self._add_widget(widget)
        return widget

    async def clear_all(self) -> None:
        for child in list(self.children):
            await child.remove()
        self.scroll_home(animate=False)

    def is_near_bottom(self, threshold: int = 2) -> bool:
        return self.max_scroll_y - self.scroll_y <= threshold

    def maybe_scroll_end(self, *, was_near_bottom: bool | None = None) -> None:
        should_scroll = self.is_near_bottom() if was_near_bottom is None else was_near_bottom
        if should_scroll:
            self.scroll_end(animate=False)

    async def _add_widget(self, widget: Widget) -> None:
        was_near_bottom = self.is_near_bottom()
        await self.mount(widget)
        self.maybe_scroll_end(was_near_bottom=was_near_bottom)
