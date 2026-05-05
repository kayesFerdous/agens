from __future__ import annotations

from collections import deque


class InputHistory:
    def __init__(self, max_items: int = 50) -> None:
        self._items: deque[str] = deque(maxlen=max_items)
        self._cursor: int | None = None

    def add(self, text: str) -> None:
        value = text.strip()
        if value and (not self._items or self._items[-1] != value):
            self._items.append(value)
        self.reset_cursor()

    def prev(self) -> str | None:
        if not self._items:
            return None
        if self._cursor is None:
            self._cursor = len(self._items) - 1
        else:
            self._cursor = max(0, self._cursor - 1)
        return self._items[self._cursor]

    def next(self) -> str | None:
        if not self._items or self._cursor is None:
            return None
        if self._cursor >= len(self._items) - 1:
            self.reset_cursor()
            return ""
        self._cursor += 1
        return self._items[self._cursor]

    def reset_cursor(self) -> None:
        self._cursor = None

    @property
    def has_cursor(self) -> bool:
        return self._cursor is not None
