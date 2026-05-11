from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option
from core.model_catalog import ALL_MODELS, PROVIDER_GROUPS, get_model_label


def _build_options(query: str, current_model: str | None) -> list[Option]:
    """Return OptionList children filtered by *query*."""
    q = query.strip().lower()

    if q:
        # Flat filtered list — no group headers when searching
        items: list[Option] = []
        for mid, lbl, _ in ALL_MODELS:
            if q in lbl.lower() or q in mid.lower():
                marker = "✓ " if mid == current_model else "  "
                items.append(
                    Option(
                        f"{marker}[bold]{lbl}[/bold]",
                        id=mid,
                    )
                )
        return items

    # Grouped — disabled header rows + model rows
    items = []
    for header, models in PROVIDER_GROUPS:
        # Group headers: uppercase, muted dividers (not headings)
        items.append(
            Option(f"[dim]{header.upper()}[/dim]", id=f"__hdr__{header}", disabled=True)
        )
        for mid, lbl in models:
            marker = "✓ " if mid == current_model else "  "
            items.append(
                Option(
                    f"{marker}[bold]{lbl}[/bold]",
                    id=mid,
                )
            )
    return items


class ModelSelectScreen(ModalScreen[str | None]):
    """Dark-panel modal that lets the user search and pick a model.

    Returns the chosen model string (e.g. ``'gemini/gemini-2.5-flash-lite'``)
    or ``None`` if the user cancels.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True),
        Binding("down", "focus_list", "Focus list", show=False),
    ]

    def __init__(self, current_model: str | None = None) -> None:
        super().__init__()
        self._current_model = current_model

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Vertical(id="model-panel"):
            # Title bar
            with Vertical(id="model-title-bar"):
                yield Static(
                    "[bold]Select model[/bold]  [dim]esc to cancel[/dim]",
                    id="model-title",
                )
            # Search field — sticky at top
            yield Input(placeholder="Search models…", id="model-search")
            # Options — fixed-height scrollable list
            yield OptionList(*_build_options("", self._current_model), id="model-list")
            # Footer hint
            yield Static(
                "  [dim]↑↓ navigate  ·  Enter select  ·  Esc cancel[/dim]",
                id="model-footer",
            )

    def on_mount(self) -> None:
        self.query_one("#model-list", OptionList).focus()
        self._scroll_to_current()

    def on_key(self, event: events.Key) -> None:
        search = self.query_one("#model-search", Input)
        if not search.has_focus and event.is_printable and event.character:
            search.focus()
            search.value += event.character
            search.cursor_position = len(search.value)
            event.prevent_default()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "model-search":
            return
        self._rebuild_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the search box moves focus to the list."""
        if event.input.id == "model-search":
            event.stop()
            self.action_focus_list()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        mid = event.option.id or ""
        if mid.startswith("__hdr__"):
            return  # disabled group header — ignore
        self.dismiss(mid)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_focus_list(self) -> None:
        self.query_one("#model-list", OptionList).focus()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _rebuild_list(self, query: str) -> None:
        ol = self.query_one("#model-list", OptionList)
        ol.clear_options()
        for item in _build_options(query, self._current_model):
            ol.add_option(item)
        self._highlight_first_selectable()

    def _highlight_first_selectable(self) -> None:
        ol = self.query_one("#model-list", OptionList)
        for idx in range(ol.option_count):
            try:
                opt = ol.get_option_at_index(idx)
                if opt.id and not opt.id.startswith("__hdr__"):
                    ol.highlighted = idx
                    return
            except Exception:
                pass

    def _scroll_to_current(self) -> None:
        if not self._current_model:
            return
        ol = self.query_one("#model-list", OptionList)
        for idx in range(ol.option_count):
            try:
                if ol.get_option_at_index(idx).id == self._current_model:
                    ol.highlighted = idx
                    return
            except Exception:
                pass
