from __future__ import annotations

from rich.style import Style
from rich.text import Text
from textual.reactive import reactive
from textual.timer import Timer
from textual.widget import Widget

BRAILLE_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class LiveSpinner(Widget):
    """
    Inline animated spinner shown during streaming.

    It appears directly in the chat flow, not as a modal or overlay.
    """

    frame: reactive[int] = reactive(0)
    label: reactive[str] = reactive("Thinking...")

    def on_mount(self) -> None:
        self._timer: Timer = self.set_interval(0.08, self._tick)

    def _tick(self) -> None:
        self.frame = (self.frame + 1) % len(BRAILLE_FRAMES)

    def render(self) -> Text:
        frame_char = BRAILLE_FRAMES[self.frame]
        width = max(0, self.app.console.width - 4)
        left = f"  {frame_char} {self.label}"
        right = "esc to stop"
        padding = max(0, width - len(left) - len(right))
        line = Text()
        line.append(left, style=Style(color="#cc785c"))
        line.append(" " * padding)
        line.append(right, style=Style(color="#3f3f3f"))
        return line

    async def stop(self) -> None:
        try:
            self._timer.stop()
        except Exception:
            pass
        try:
            await self.remove()
        except Exception:
            pass
