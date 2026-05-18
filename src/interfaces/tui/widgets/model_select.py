from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from rich.markup import escape
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from db.database import async_session
from interfaces.api.models.router import list_models


CACHE_TTL_SECONDS = 60
API_KEYS_COMMAND_HINT = "/keys"

_MODEL_CACHE: dict[str, Any] | None = None
_MODEL_CACHE_TS = 0.0


@dataclass(frozen=True)
class RowMeta:
    kind: str
    value: str | None = None
    provider_id: str | None = None
    provider_name: str | None = None
    disabled: bool = False


async def _fetch_models() -> tuple[dict[str, Any] | None, str | None]:
    global _MODEL_CACHE, _MODEL_CACHE_TS

    now = time.monotonic()
    if _MODEL_CACHE is not None and now - _MODEL_CACHE_TS < CACHE_TTL_SECONDS:
        return _MODEL_CACHE, None

    try:
        async with async_session() as db:
            response = await list_models(db)
            _MODEL_CACHE = response.model_dump(mode="json")
            _MODEL_CACHE_TS = now
            return _MODEL_CACHE, None
    except Exception:
        if _MODEL_CACHE is not None:
            return _MODEL_CACHE, "Could not load model list - using cached data"
        return None, "Could not load model list"


def get_model_label(model_id: str | None) -> str:
    if not model_id:
        return "Auto ✦"
    if _MODEL_CACHE:
        for provider in _MODEL_CACHE.get("providers", []):
            for model in provider.get("models", []):
                value = f"{provider['id']}/{model['id']}"
                if value == model_id:
                    return f"{provider['id']}/{model['name']}"
    return model_id


def _speed_tag(speed_label: str) -> str:
    value = speed_label.lower()
    if "very" in value:
        return "v.fast"
    if "fast" in value:
        return "fast"
    if "moderate" in value:
        return "mod"
    return "slow"


def _matches(query: str, provider: dict[str, Any], model: dict[str, Any]) -> bool:
    if not query:
        return True
    haystack = " ".join(
        [
            provider.get("name", ""),
            provider.get("id", ""),
            model.get("name", ""),
            model.get("id", ""),
            model.get("speed_label", ""),
        ]
    ).lower()
    return query.lower() in haystack


def _highlight(text: str, query: str) -> str:
    if not query:
        return escape(text)
    lower = text.lower()
    needle = query.lower()
    start = lower.find(needle)
    if start == -1:
        return escape(text)
    end = start + len(query)
    return (
        escape(text[:start])
        + "[yellow]"
        + escape(text[start:end])
        + "[/yellow]"
        + escape(text[end:])
    )


def _build_model_row(
    provider: dict[str, Any],
    model: dict[str, Any],
    current_model: str | None,
    query: str,
) -> str:
    value = f"{provider['id']}/{model['id']}"
    marker = "●" if value == current_model else "○"
    disabled = not provider.get("has_active_key") or model.get("status") == "no_key"
    name = _highlight(str(model.get("name", model.get("id", ""))), query)
    tags = []
    if model.get("free_tier"):
        tags.append("[#50fa7b][Free][/#50fa7b]")
    tags.append(f"[#A99DD1][{_speed_tag(str(model.get('speed_label', '')))}][/#A99DD1]")
    if model.get("status") == "cooldown":
        tags.append("[#f1fa8c][rate limited][/#f1fa8c]")
    row = f"  {marker} {name} {' '.join(tags)}"
    return f"[dim]{row}[/dim]" if disabled else row


def _build_options(
    data: dict[str, Any] | None,
    query: str,
    current_model: str | None,
) -> tuple[list[Option], dict[str, RowMeta]]:
    rows: list[Option] = [
        Option(
            "[dim italic]  Auto (router picks best)[/dim italic]\n"
            "[dim]    Let Agens pick the fastest model[/dim]",
            id="__auto__",
        )
    ]
    meta = {"__auto__": RowMeta(kind="auto")}

    if not data:
        return rows, meta

    q = query.strip()
    for provider in data.get("providers", []):
        models = [model for model in provider.get("models", []) if _matches(q, provider, model)]
        if not models:
            continue

        provider_name = str(provider.get("name", provider.get("id", "")))
        header = f"  [bold]{_highlight(provider_name, q)}[/bold]"
        if not provider.get("has_active_key"):
            header += " [dim](no key)[/dim]"
        header_id = f"__hdr__{provider.get('id')}"
        rows.append(Option(header, id=header_id, disabled=True))
        meta[header_id] = RowMeta(kind="header")

        for model in models:
            value = f"{provider['id']}/{model['id']}"
            option_id = f"__model__{value}"
            disabled = not provider.get("has_active_key") or model.get("status") == "no_key"
            rows.append(
                Option(
                    _build_model_row(provider, model, current_model, q),
                    id=option_id,
                )
            )
            meta[option_id] = RowMeta(
                kind="model",
                value=value,
                provider_id=str(provider.get("id")),
                provider_name=provider_name,
                disabled=disabled,
            )

        if not provider.get("has_active_key"):
            hint_id = f"__hint__{provider.get('id')}"
            rows.append(
                Option(
                    f"    [dim]Add key in Settings to enable - type {API_KEYS_COMMAND_HINT}[/dim]",
                    id=hint_id,
                    disabled=True,
                )
            )
            meta[hint_id] = RowMeta(kind="hint")

    return rows, meta


class ModelSelectScreen(ModalScreen[dict[str, str | None] | None]):
    """Searchable model selector fed by the shared model catalog."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True),
        Binding("down", "focus_list", "Focus list", show=False),
    ]

    def __init__(self, current_model: str | None = None) -> None:
        super().__init__()
        self._current_model = current_model
        self._data: dict[str, Any] | None = None
        self._row_meta: dict[str, RowMeta] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="model-panel"):
            with Vertical(id="model-title-bar"):
                yield Static(
                    "[bold]Select Model[/bold]  [dim](ESC to close)[/dim]",
                    id="model-title",
                )
            yield Input(placeholder="search:", id="model-search")
            yield Static("[dim]Loading models...[/dim]", id="model-status")
            yield OptionList(id="model-list")
            yield Static(
                "  [dim]↑↓ move · Enter select · / search[/dim]",
                id="model-footer",
            )

    async def on_mount(self) -> None:
        await self._load()
        self.query_one("#model-list", OptionList).focus()
        self._scroll_to_current()

    def on_key(self, event: events.Key) -> None:
        search = self.query_one("#model-search", Input)
        if not search.has_focus and event.key == "/":
            search.focus()
            event.prevent_default()
            return
        if not search.has_focus and event.is_printable and event.character:
            search.focus()
            search.value += event.character
            search.cursor_position = len(search.value)
            event.prevent_default()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "model-search":
            return
        self._rebuild_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "model-search":
            event.stop()
            self.action_focus_list()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id or ""
        meta = self._row_meta.get(option_id)
        if meta is None:
            return
        if meta.kind == "auto":
            self.dismiss({"model": None})
            return
        if meta.kind != "model":
            return
        if meta.disabled:
            self._show_disabled_message(meta.provider_name or "provider")
            return
        self.dismiss({"model": meta.value})

    async def _load(self) -> None:
        self._data, message = await _fetch_models()
        self.query_one("#model-status", Static).update(
            f"[#f1fa8c]{message}[/#f1fa8c]" if message else ""
        )
        self._rebuild_list("")

    def _rebuild_list(self, query: str) -> None:
        ol = self.query_one("#model-list", OptionList)
        ol.clear_options()
        options, self._row_meta = _build_options(self._data, query, self._current_model)
        for item in options:
            ol.add_option(item)
        self._highlight_first_selectable()

    def _highlight_first_selectable(self) -> None:
        ol = self.query_one("#model-list", OptionList)
        for idx in range(ol.option_count):
            try:
                opt = ol.get_option_at_index(idx)
                meta = self._row_meta.get(opt.id or "")
                if meta and meta.kind in {"auto", "model"}:
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
                opt = ol.get_option_at_index(idx)
                meta = self._row_meta.get(opt.id or "")
                if meta and meta.value == self._current_model:
                    ol.highlighted = idx
                    return
            except Exception:
                pass

    def _show_disabled_message(self, provider: str) -> None:
        self.query_one("#model-status", Static).update(
            f"[#f1fa8c]No {provider} key found - type {API_KEYS_COMMAND_HINT} to open API Keys.[/#f1fa8c]"
        )

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_focus_search(self) -> None:
        self.query_one("#model-search", Input).focus()

    def action_focus_list(self) -> None:
        self.query_one("#model-list", OptionList).focus()
