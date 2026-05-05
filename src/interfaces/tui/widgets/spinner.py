from __future__ import annotations

from textual.app import ComposeResult
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static


class StreamingSpinner(Widget):
    FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    frame_index = reactive(0)

    def compose(self) -> ComposeResult:
        yield Static(self._render(), id="spinner-line")

    def on_mount(self) -> None:
        self.set_interval(0.08, self._tick)

    def watch_frame_index(self) -> None:
        try:
            self.query_one("#spinner-line", Static).update(self._render())
        except NoMatches:
            pass

    def _tick(self) -> None:
        self.frame_index = (self.frame_index + 1) % len(self.FRAMES)

    def _render(self) -> str:
        frame = self.FRAMES[self.frame_index]
        return f"{frame} Thinking...                           [ESC to stop]"
