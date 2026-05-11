"""TUI screens for API key management — list & add."""
from __future__ import annotations

import asyncio

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Input, Static, Button, OptionList
from textual.widgets.option_list import Option

from db.database import async_session
from db.models import APIKey, KeyStatus
from db.repositories.api_key import APIKeyRepository
from services.api_key_manager import APIKeyManager
from config.settings import settings
from cryptography.fernet import Fernet


# ─── Visual constants ────────────────────────────────────────────────

_STATUS_DISPLAY: dict[KeyStatus, tuple[str, str, str]] = {
    KeyStatus.ACTIVE:       ("●", "active",       "#50fa7b"),
    KeyStatus.INACTIVE:     ("○", "inactive",     "#56524C"),
    KeyStatus.RATE_LIMITED: ("◐", "rate-limited", "#f1fa8c"),
    KeyStatus.EXHAUSTED:    ("✕", "exhausted",    "#ff5555"),
    KeyStatus.INVALID:      ("✕", "invalid",      "#ff5555"),
}

_PROVIDER_ICON: dict[str, str] = {
    "gemini": "◆",
    "openai": "◇",
    "anthropic": "△",
}

# Fixed column widths — plain chars only, no markup
_W_PROV  = 12
_W_HINT  = 14
_W_STAT  = 16
_W_USED  = 16


def _time_plain(dt) -> str:
    if dt is None:
        return "never"
    return dt.strftime("%b %d, %H:%M")


def _build_header() -> Text:
    """Table header row: small, muted, spaced-out labels."""
    t = Text()
    t.append("   ")
    t.append("PROVIDER".ljust(_W_PROV), style="#56524C")
    t.append("HINT".ljust(_W_HINT),     style="#56524C")
    t.append("STATUS".ljust(_W_STAT),   style="#56524C")
    t.append("LAST USED".ljust(_W_USED), style="#56524C")
    t.append("LABEL",                    style="#56524C")
    return t


def _build_row(key: APIKey) -> Text:
    t = Text()
    icon = _PROVIDER_ICON.get(key.provider, "·")
    t.append(f" {icon} ", style="dim")
    t.append(key.provider.ljust(_W_PROV), style="bold")
    # HINT column: accent-mid violet, NOT copper
    t.append(key.key_hint.ljust(_W_HINT), style="#A99DD1")

    s_icon, s_label, s_color = _STATUS_DISPLAY.get(
        key.status, ("?", key.status.value, "#F5F0E8")
    )
    t.append(f"{s_icon} ", style=s_color)
    t.append(s_label.ljust(_W_STAT - 2), style=s_color)

    t.append(_time_plain(key.last_used_at).ljust(_W_USED), style="dim")
    t.append(key.label or "—", style="dim")
    return t


# ─── KeyList: OptionList that doesn't swallow our action keys ────────

class KeyList(OptionList):
    """OptionList that passes t/d/y/n/esc up to the screen unchanged."""

    _PASSTHROUGH = {"t", "d", "y", "n", "escape"}

    def _on_key(self, event: events.Key) -> None:
        if event.key in self._PASSTHROUGH or event.character in self._PASSTHROUGH:
            # Don't call super — let the event bubble to screen bindings
            return
        super()._on_key(event)


# ═════════════════════════════════════════════════════════════════════
#  List Keys Screen
# ═════════════════════════════════════════════════════════════════════

class APIKeyListScreen(ModalScreen[None]):
    """Interactive key list — t toggle, d delete (y/N confirm)."""

    BINDINGS = [
        Binding("escape", "cancel",        "Close",   priority=True),
        Binding("ctrl+c", "cancel",        "Close",   priority=True),
        Binding("t",      "toggle_status", "Toggle",  priority=True, show=False),
        Binding("d",      "start_delete",  "Delete",  priority=True, show=False),
        Binding("y",      "confirm_yes",   "Confirm", priority=True, show=False),
        Binding("n",      "confirm_no",    "Deny",    priority=True, show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._keys: list[APIKey] = []
        self._pending_delete_id: str | None = None

    # ── Layout ────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        with Vertical(id="apikey-panel"):
            with Vertical(id="apikey-title-bar"):
                yield Static(
                    "[bold]API Keys[/bold]  [dim]esc to close[/dim]",
                    id="apikey-title",
                )
            yield Static("", id="apikey-header-row")
            yield KeyList(id="apikey-list")
            yield Static("", id="apikey-summary")
            yield Static("", id="apikey-footer")

    async def on_mount(self) -> None:
        self._set_footer_normal()
        await self._load_keys()

    # ── Footer helpers ────────────────────────────────────────────

    def _set_footer_normal(self) -> None:
        """Keyboard hint bar: muted text, hotkeys in accent-mid violet."""
        footer = self.query_one("#apikey-footer", Static)
        t = Text()
        t.append("  ↑↓", style="#56524C")
        t.append(" navigate  ·  ", style="#56524C")
        t.append("t", style="bold #A99DD1")
        t.append(" toggle  ·  ", style="#56524C")
        t.append("d", style="bold #A99DD1")
        t.append(" delete  ·  ", style="#56524C")
        t.append("esc", style="bold #A99DD1")
        t.append(" close", style="#56524C")
        footer.update(t)

    def _set_footer_confirm(self, key: APIKey) -> None:
        footer = self.query_one("#apikey-footer", Static)
        t = Text()
        t.append("  Delete ", style="bold #ff5555")
        t.append(key.key_hint, style="#A99DD1")
        t.append(f" ({key.provider})?  ", style="#56524C")
        t.append("y", style="bold #F5F0E8")
        t.append("  /  ", style="#56524C")
        t.append("N", style="#56524C")
        footer.update(t)

    # ── Data loading ──────────────────────────────────────────────

    async def _load_keys(self) -> None:
        ol = self.query_one("#apikey-list", KeyList)
        header = self.query_one("#apikey-header-row", Static)
        summary = self.query_one("#apikey-summary", Static)

        try:
            async with async_session() as db:
                repo = APIKeyRepository(db)
                self._keys = await repo.list_keys(limit=50)
        except Exception as exc:
            header.update("")
            summary.update(f"[red]Error:[/red] {exc}")
            return

        ol.clear_options()

        if not self._keys:
            header.update("")
            summary.update(
                "  [dim]No API keys yet.  Use [bold]/addkey[/bold] to add one.[/dim]"
            )
            return

        header.update(_build_header())

        for key in self._keys:
            ol.add_option(Option(_build_row(key), id=key.id))

        n = len(self._keys)
        summary.update(f"  [dim]{n} key{'s' if n != 1 else ''} total[/dim]")

        ol.focus()
        if ol.option_count:
            ol.highlighted = 0

    # ── Highlighted key helper ────────────────────────────────────

    def _highlighted_key(self) -> APIKey | None:
        ol = self.query_one("#apikey-list", KeyList)
        idx = ol.highlighted
        if idx is None:
            return None
        try:
            opt = ol.get_option_at_index(idx)
            return next((k for k in self._keys if k.id == opt.id), None)
        except Exception:
            return None

    # ── Actions (priority bindings fire before OptionList._on_key) ─

    def action_toggle_status(self) -> None:
        if self._pending_delete_id is not None:
            self._cancel_delete()
            return
        asyncio.create_task(self._do_toggle())

    def action_start_delete(self) -> None:
        if self._pending_delete_id is not None:
            self._cancel_delete()
            return
        key = self._highlighted_key()
        if key is None:
            return
        self._pending_delete_id = key.id
        self._set_footer_confirm(key)

    def action_confirm_yes(self) -> None:
        if self._pending_delete_id is not None:
            asyncio.create_task(self._confirm_delete())

    def action_confirm_no(self) -> None:
        if self._pending_delete_id is not None:
            self._cancel_delete()

    # ── Toggle ────────────────────────────────────────────────────

    async def _do_toggle(self) -> None:
        key = self._highlighted_key()
        if key is None:
            return

        new_status = (
            KeyStatus.INACTIVE if key.status == KeyStatus.ACTIVE
            else KeyStatus.ACTIVE
        )

        try:
            async with async_session() as db:
                repo = APIKeyRepository(db)
                if new_status == KeyStatus.ACTIVE:
                    await repo.clear_cooldown(key.id)
                else:
                    await repo.update_status(key.id, new_status)
        except Exception:
            return

        ol = self.query_one("#apikey-list", KeyList)
        prev_idx = ol.highlighted
        await self._load_keys()
        if prev_idx is not None and prev_idx < ol.option_count:
            ol.highlighted = prev_idx

    # ── Delete ────────────────────────────────────────────────────

    def _cancel_delete(self) -> None:
        self._pending_delete_id = None
        self._set_footer_normal()

    async def _confirm_delete(self) -> None:
        key_id = self._pending_delete_id
        self._pending_delete_id = None
        if key_id is None:
            return

        try:
            async with async_session() as db:
                repo = APIKeyRepository(db)
                await repo.delete_by_id(key_id)
        except Exception:
            pass

        self._set_footer_normal()

        ol = self.query_one("#apikey-list", KeyList)
        prev_idx = ol.highlighted or 0
        await self._load_keys()
        if ol.option_count:
            ol.highlighted = min(prev_idx, ol.option_count - 1)

    # ── Dismiss ───────────────────────────────────────────────────

    def action_cancel(self) -> None:
        if self._pending_delete_id is not None:
            self._cancel_delete()
            return
        self.dismiss(None)


# ═════════════════════════════════════════════════════════════════════
#  Add Key Screen
# ═════════════════════════════════════════════════════════════════════

class APIKeyAddScreen(ModalScreen[str | None]):
    """Minimal form to add a new API key."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+c", "cancel", "Cancel", priority=True),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="addkey-panel"):
            with Vertical(id="addkey-title-bar"):
                yield Static(
                    "[bold]Add API Key[/bold]  [dim]esc to cancel[/dim]",
                    id="addkey-title",
                )

            with Vertical(id="addkey-form"):
                yield Static("[#8C877E]Provider[/#8C877E]", classes="field-label")
                yield Static(
                    "[#A99DD1]gemini · openai · anthropic[/#A99DD1]",
                    classes="field-hint",
                )
                yield Input(placeholder="e.g. gemini", id="addkey-provider")

                yield Static("[#8C877E]API Key[/#8C877E]", classes="field-label")
                yield Input(placeholder="Paste your API key", id="addkey-key", password=True)

                yield Static(
                    "[#8C877E]Label[/#8C877E]  [#56524C](optional)[/#56524C]",
                    classes="field-label",
                )
                yield Input(placeholder="e.g. Prod-Gemini-Main", id="addkey-label")

            yield Static("", id="addkey-status")

            with Horizontal(id="addkey-actions"):
                yield Button("Save",   id="addkey-save",   variant="primary")
                yield Button("Cancel", id="addkey-cancel", variant="default")

            yield Static(
                "  [dim]Tab to navigate  ·  Enter to save[/dim]",
                id="addkey-footer",
            )

    def on_mount(self) -> None:
        self.query_one("#addkey-provider", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "addkey-cancel":
            self.dismiss(None)
        elif event.button.id == "addkey-save":
            asyncio.create_task(self._save_key())

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in {"addkey-provider", "addkey-key", "addkey-label"}:
            asyncio.create_task(self._save_key())

    async def _save_key(self) -> None:
        status = self.query_one("#addkey-status", Static)
        provider = self.query_one("#addkey-provider", Input).value.strip().lower()
        raw_key = self.query_one("#addkey-key", Input).value.strip()
        label = self.query_one("#addkey-label", Input).value.strip() or None

        if not provider:
            status.update("[#ff5555]✕  Provider is required[/#ff5555]")
            self.query_one("#addkey-provider", Input).focus()
            return
        if not raw_key:
            status.update("[#ff5555]✕  API key is required[/#ff5555]")
            self.query_one("#addkey-key", Input).focus()
            return

        status.update("[dim]Saving…[/dim]")
        try:
            fernet = Fernet(settings.FERNET_SECRET)
            async with async_session() as db:
                repo = APIKeyRepository(db)
                manager = APIKeyManager(repo, fernet)
                created = await manager.add_key(
                    raw_key=raw_key, provider=provider, label=label,
                )
            self.dismiss(
                f"[#50fa7b]✓[/#50fa7b]  Key added — "
                f"[#A99DD1]{created.key_hint}[/#A99DD1] ({created.provider})"
            )
        except ValueError as exc:
            status.update(f"[#ff5555]✕  {exc}[/#ff5555]")
        except Exception as exc:
            status.update(f"[red]Error:[/red] {exc}")

    def action_cancel(self) -> None:
        self.dismiss(None)
