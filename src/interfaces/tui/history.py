from __future__ import annotations


class InputHistory:
    def __init__(self, max_size: int = 50, max_items: int | None = None) -> None:
        self._items: list[str] = []
        self._cursor: int = -1
        self._max = max_items or max_size

    def add(self, text: str) -> None:
        value = text.strip()
        if value and (not self._items or self._items[-1] != value):
            self._items.append(value)
            if len(self._items) > self._max:
                self._items.pop(0)
        self.reset()

    def prev(self) -> str | None:
        if not self._items:
            return None
        self._cursor = max(0, self._cursor - 1)
        return self._items[self._cursor]

    def next(self) -> str | None:
        if not self._items:
            return None
        self._cursor = min(len(self._items), self._cursor + 1)
        if self._cursor == len(self._items):
            return ""
        return self._items[self._cursor]

    def reset(self) -> None:
        self._cursor = len(self._items)

    def reset_cursor(self) -> None:
        self.reset()

    @property
    def has_cursor(self) -> bool:
        return self._cursor != len(self._items)
