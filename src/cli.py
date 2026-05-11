"""CLI entry point for managing the assistant."""
from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config.config_manager import ConfigManager
from config.runtime import get_runtime_root, initialize_runtime
from config.settings import settings
from cryptography.fernet import Fernet
from db.database import async_session
from db.models import KeyStatus
from db.repositories.api_key import APIKeyRepository
from services.api_key_manager import APIKeyManager
from services.settings_service import SettingsService


app = typer.Typer(help="Assistant CLI")
apikey_app = typer.Typer(help="Manage API keys.")
safety_app = typer.Typer(help="Safety mode controls.")
telegram_app = typer.Typer(help="Telegram integration.")

app.add_typer(apikey_app, name="apikey")
app.add_typer(safety_app, name="safety")
app.add_typer(telegram_app, name="telegram")

console = Console()
error_console = Console(stderr=True)

_INTERFACE_STATE_FILE = get_runtime_root() / "interfaces.json"
_KNOWN_INTERFACES = ("web", "telegram", "tui")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "asyncio.run()" in str(exc):
            error_console.print("[red]Error:[/red] Command cannot run inside an active event loop.")
            raise typer.Exit(code=1)
        raise


def _mask_secret(value: str, visible: int = 4) -> str:
    if not value:
        return ""
    tail = value[-visible:] if len(value) >= visible else value
    mask_len = max(8, len(value) - len(tail))
    return "*" * mask_len + tail


def _mask_hint(hint: str | None) -> str:
    if not hint:
        return ""
    tail = hint.split("...")[-1]
    return "*" * 8 + tail


def _pid_running(pid: int) -> bool:
    return Path(f"/proc/{pid}").exists()


def _load_interface_state() -> dict[str, Any] | None:
    if not _INTERFACE_STATE_FILE.exists():
        return None
    try:
        return json.loads(_INTERFACE_STATE_FILE.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _interface_details(name: str) -> str:
    if name == "web":
        host = settings.WEB_HOST
        if host in {"0.0.0.0", "localhost"}:
            host = "127.0.0.1"
        return f"http://{host}:{settings.WEB_PORT}"
    if name == "telegram":
        if settings.WEBHOOK_HOST:
            return f"webhook {settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}"
        return "long polling"
    if name == "tui":
        return "terminal UI"
    return ""


def _web_shutdown_url() -> str:
    host = settings.WEB_HOST
    if host in {"0.0.0.0", "localhost"}:
        host = "127.0.0.1"
    return f"http://{host}:{settings.WEB_PORT}/shutdown"


def _request_web_shutdown() -> bool:
    url = _web_shutdown_url()
    req = Request(url, method="POST", headers={"x-vela-action": "shutdown"})
    try:
        with urlopen(req, timeout=3):
            return True
    except (HTTPError, URLError, OSError):
        return False


# ---------------------------------------------------------------------------
# API key commands
# ---------------------------------------------------------------------------


@apikey_app.command("add")
def apikey_add(
    label: str = typer.Argument(..., help="Human-friendly label for the key."),
    provider: str = typer.Argument(..., help="Provider name (e.g. gemini)."),
    api_key: str = typer.Argument(..., help="The raw API key value."),
) -> None:
    """Add a new API key."""
    initialize_runtime()

    label = label.strip()
    provider = provider.strip()
    api_key = api_key.strip()

    if not label:
        error_console.print("[red]Error:[/red] Label cannot be empty.")
        raise typer.Exit(code=1)
    if not provider:
        error_console.print("[red]Error:[/red] Provider cannot be empty.")
        raise typer.Exit(code=1)
    if not api_key:
        error_console.print("[red]Error:[/red] API key cannot be empty.")
        raise typer.Exit(code=1)

    async def _add() -> None:
        async with async_session() as db:
            repo = APIKeyRepository(db)
            existing = await repo.get_by_label(label)
            if existing:
                raise ValueError(f"Label '{label}' already exists.")
            manager = APIKeyManager(repo, Fernet(settings.FERNET_SECRET))
            await manager.add_key(raw_key=api_key, provider=provider, label=label)

    try:
        _run(_add())
    except ValueError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    masked = _mask_secret(api_key)
    console.print(
        f"Saved API key '{label}' ({provider}). Key: {masked}"
    )


@apikey_app.command("list")
def apikey_list() -> None:
    """List stored API keys."""
    initialize_runtime()

    async def _list():
        async with async_session() as db:
            repo = APIKeyRepository(db)
            return await repo.list_keys(limit=500)

    try:
        keys = _run(_list())
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if not keys:
        console.print("No API keys found. Add one with: assistant apikey add")
        return

    table = Table(title="API Keys", header_style="bold")
    table.add_column("Label")
    table.add_column("Provider")
    table.add_column("Key", no_wrap=True)
    table.add_column("Status")

    for key in keys:
        if key.status == KeyStatus.ACTIVE:
            status_text = Text("Active", style="green")
        elif key.status == KeyStatus.INACTIVE:
            status_text = Text("Inactive", style="dim")
        else:
            extra = key.status.value.replace("_", " ")
            status_text = Text(f"Inactive ({extra})", style="dim")

        table.add_row(
            key.label or "-",
            key.provider,
            _mask_hint(key.key_hint),
            status_text,
        )

    console.print(table)


@apikey_app.command("remove")
def apikey_remove(
    label: str = typer.Argument(..., help="Label of the key to remove."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Remove an API key by label."""
    initialize_runtime()
    label = label.strip()

    if not label:
        error_console.print("[red]Error:[/red] Label cannot be empty.")
        raise typer.Exit(code=1)

    if not yes and not typer.confirm(f"Remove key '{label}'?", default=False):
        console.print("Cancelled.")
        raise typer.Exit(code=0)

    async def _remove():
        async with async_session() as db:
            repo = APIKeyRepository(db)
            key = await repo.get_by_label(label)
            if not key:
                raise ValueError(f"Label '{label}' not found.")
            return await repo.delete_by_id(key.id)

    try:
        _run(_remove())
    except ValueError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"Removed API key '{label}'.")


@apikey_app.command("toggle")
def apikey_toggle(
    label: str = typer.Argument(..., help="Label of the key to toggle."),
) -> None:
    """Toggle an API key between active and inactive."""
    initialize_runtime()
    label = label.strip()

    if not label:
        error_console.print("[red]Error:[/red] Label cannot be empty.")
        raise typer.Exit(code=1)

    async def _toggle() -> KeyStatus:
        async with async_session() as db:
            repo = APIKeyRepository(db)
            key = await repo.get_by_label(label)
            if not key:
                raise ValueError(f"Label '{label}' not found.")
            if key.status not in {KeyStatus.ACTIVE, KeyStatus.INACTIVE}:
                human = key.status.value.replace("_", " ")
                raise ValueError(f"Key '{label}' is {human} and cannot be toggled.")

            new_status = (
                KeyStatus.INACTIVE if key.status == KeyStatus.ACTIVE
                else KeyStatus.ACTIVE
            )
            if new_status == KeyStatus.ACTIVE:
                await repo.clear_cooldown(key.id)
            else:
                await repo.update_status(key.id, new_status)
            return new_status

    try:
        new_status = _run(_toggle())
    except ValueError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if new_status == KeyStatus.ACTIVE:
        console.print(Text(f"Key '{label}' is now Active.", style="green"))
    else:
        console.print(Text(f"Key '{label}' is now Inactive.", style="dim"))


# ---------------------------------------------------------------------------
# Safety mode
# ---------------------------------------------------------------------------


@safety_app.command("toggle")
def safety_toggle() -> None:
    """Toggle safety mode on or off."""
    initialize_runtime()

    async def _toggle() -> bool:
        async with async_session() as db:
            service = SettingsService(db)
            current = await service.get_settings()
            updated = await service.update_settings(safety_mode=not current.safety_mode)
            return updated.safety_mode

    try:
        enabled = _run(_toggle())
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if enabled:
        console.print(Panel(Text("Safety mode: ON", style="green"), title="Safety"))
    else:
        console.print(Panel(Text("Safety mode: OFF", style="yellow"), title="Safety"))


@safety_app.command("status")
def safety_status() -> None:
    """Show the current safety mode state."""
    initialize_runtime()

    async def _status() -> bool:
        async with async_session() as db:
            service = SettingsService(db)
            current = await service.get_settings()
            return current.safety_mode

    try:
        enabled = _run(_status())
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if enabled:
        console.print(Panel(Text("Safety mode: ON", style="green"), title="Safety"))
    else:
        console.print(Panel(Text("Safety mode: OFF", style="yellow"), title="Safety"))


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


@app.command("interfaces")
def interfaces_status() -> None:
    """List running interfaces."""
    initialize_runtime()

    state = _load_interface_state()
    running: set[str] = set()
    stale_state = False

    if state and isinstance(state, dict):
        pid = state.get("pid")
        if isinstance(pid, int) and _pid_running(pid):
            iface_map = state.get("interfaces") or {}
            running = {name for name in iface_map if name in _KNOWN_INTERFACES}
        else:
            stale_state = True

    table = Table(title="Interfaces", header_style="bold")
    table.add_column("Interface")
    table.add_column("Status")
    table.add_column("Details")

    for name in _KNOWN_INTERFACES:
        is_running = name in running
        status_text = Text("running", style="green") if is_running else Text("stopped", style="dim")
        details = _interface_details(name) if is_running else "not running"
        if stale_state and not running:
            details = "stale runtime state"
        table.add_row(name, status_text, details)

    console.print(table)

    if not running:
        console.print("No interfaces running. Start one with: vela web")


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


@app.command("shutdown")
def shutdown(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Gracefully shut down the assistant."""
    initialize_runtime()

    if not yes and not typer.confirm("Shut down the assistant and all interfaces?", default=False):
        console.print("Cancelled.")
        raise typer.Exit(code=0)

    state = _load_interface_state()
    if not state or "pid" not in state:
        error_console.print("[red]Error:[/red] No running assistant process found.")
        raise typer.Exit(code=1)

    pid = state.get("pid")
    if not isinstance(pid, int) or not _pid_running(pid):
        error_console.print("[red]Error:[/red] No running assistant process found.")
        raise typer.Exit(code=1)

    iface_map = state.get("interfaces") or {}
    if "web" in iface_map and _request_web_shutdown():
        console.print("Shutdown requested via web interface.")
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print("Shutdown signal sent.")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


@telegram_app.command("set-token")
def telegram_set_token(
    token: str = typer.Argument(..., help="Telegram bot token."),
) -> None:
    """Set the Telegram bot token."""
    initialize_runtime()

    token = token.strip()
    if not token:
        error_console.print("[red]Error:[/red] Token cannot be empty.")
        raise typer.Exit(code=1)

    manager = ConfigManager()
    try:
        manager.update_config({"telegram_token": token})
    except ValueError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)
    except OSError as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    console.print(f"Telegram token saved. Token: {_mask_secret(token)}")


def main() -> None:
    """Console entry point."""
    app()


if __name__ == "__main__":
    main()
