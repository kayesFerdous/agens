"""
main.py — unified launcher and CLI for the AI assistant.

Examples:
  agens web
  agens telegram
  agens tui
  agens start web telegram
  agens apikey list
  agens safety toggle
"""
from __future__ import annotations

import asyncio
import ctypes
import errno
import functools
import json
import os
import signal
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .app_bootstrap import bootstrap_database, bootstrap_runtime
from config.config_manager import ConfigManager
from config.settings import settings
from config.runtime import get_runtime_root
from config.logging import get_logger, setup_logging
from cryptography.fernet import Fernet
from db.database import async_session
from db.models import KeyStatus
from db.repositories.api_key import APIKeyRepository
from services.api_key_manager import APIKeyManager
from services.settings_service import SettingsService
from interfaces.api_key_state import (
    NO_API_KEYS_CLI_MESSAGE,
    user_key_unavailable_message,
    has_any_api_keys,
)
from llm.errors import LLMUnavailableError


setup_logging("ERROR" if settings.PRODUCTION else "INFO")
logger = get_logger(__name__)

app = typer.Typer(help="Agens CLI", no_args_is_help=True)
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
_INTERACTIVE_INTERFACES = {"tui"}
VALID_INTERFACES = set(_KNOWN_INTERFACES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _package_version() -> str:
    try:
        return package_version("agens")
    except PackageNotFoundError:
        return "0+local"


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the installed Agens version and exit.",
    ),
) -> None:
    """Agens command line interface."""
    if version:
        console.print(f"agens {_package_version()}")
        raise typer.Exit(code=0)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(code=0)


def _run(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError as exc:
        if "asyncio.run()" in str(exc):
            error_console.print("[red]Error:[/red] Command cannot run inside an active event loop.")
            raise typer.Exit(code=1)
        raise


def _with_database(command):
    @functools.wraps(command)
    def wrapper(*args, **kwargs):
        _run(bootstrap_database())
        return command(*args, **kwargs)

    return wrapper


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


def _is_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        synchronize = 0x00100000
        error_access_denied = 5
        wait_timeout = 0x00000102
        wait_failed = 0xFFFFFFFF
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            if kernel32.GetLastError() == error_access_denied:
                return True
            return False
        try:
            status = kernel32.WaitForSingleObject(handle, 0)
            return status == wait_timeout and status != wait_failed
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


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


def _web_base_url() -> str:
    host = settings.WEB_HOST
    if host in {"0.0.0.0", "localhost"}:
        host = "127.0.0.1"
    return f"http://{host}:{settings.WEB_PORT}"


def _web_shutdown_url() -> str:
    return f"{_web_base_url()}/shutdown"


def _web_health_url() -> str:
    return f"{_web_base_url()}/health"


def _request_web_shutdown() -> bool:
    url = _web_shutdown_url()
    req = Request(url, method="POST", headers={"x-agens-action": "shutdown"})
    try:
        with urlopen(req, timeout=3):
            return True
    except (HTTPError, URLError, OSError):
        return False


def _write_interface_state(selected: list[str], *, pid: int | None = None) -> None:
    process_pid = pid if pid is not None else os.getpid()
    existing = _load_interface_state()
    interfaces: dict[str, Any] = {}
    started_at = datetime.now(timezone.utc).isoformat()

    if existing and isinstance(existing, dict):
        raw_interfaces = existing.get("interfaces")
        if isinstance(raw_interfaces, dict):
            interfaces = {
                name: details
                for name, details in raw_interfaces.items()
                if name in VALID_INTERFACES and isinstance(details, dict)
            }
        existing_started_at = existing.get("started_at")
        if isinstance(existing_started_at, str):
            started_at = existing_started_at

    for name in selected:
        interfaces[name] = {"status": "running", "pid": process_pid}

    pids = sorted({
        details["pid"]
        for details in interfaces.values()
        if isinstance(details.get("pid"), int)
    })
    data = {
        "pid": pids[0] if len(pids) == 1 else None,
        "pids": pids,
        "started_at": started_at,
        "interfaces": interfaces,
    }
    try:
        _INTERFACE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _INTERFACE_STATE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to write interface state: %s", exc)


def _clear_interface_state() -> None:
    try:
        if _INTERFACE_STATE_FILE.exists():
            _INTERFACE_STATE_FILE.unlink()
    except OSError as exc:
        logger.warning("Failed to clear interface state: %s", exc)


def _remove_interface_state(selected: list[str], *, pid: int | None = None) -> None:
    state = _load_interface_state()
    if not state or not isinstance(state, dict):
        return

    raw_interfaces = state.get("interfaces")
    if not isinstance(raw_interfaces, dict):
        _clear_interface_state()
        return

    interfaces = dict(raw_interfaces)
    for name in selected:
        details = interfaces.get(name)
        if not isinstance(details, dict):
            interfaces.pop(name, None)
            continue
        if pid is None or details.get("pid") == pid:
            interfaces.pop(name, None)

    if not interfaces:
        _clear_interface_state()
        return

    pids = sorted({
        details["pid"]
        for details in interfaces.values()
        if isinstance(details, dict) and isinstance(details.get("pid"), int)
    })
    state["interfaces"] = interfaces
    state["pid"] = pids[0] if len(pids) == 1 else None
    state["pids"] = pids
    try:
        _INTERFACE_STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Failed to update interface state: %s", exc)


def _terminate_process(pid: int) -> None:
    if os.name == "nt":
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        process_terminate = 0x0001
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel32.TerminateProcess.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.OpenProcess(process_terminate, False, pid)
        if not handle:
            raise OSError(kernel32.GetLastError(), "Failed to open process")
        try:
            if not kernel32.TerminateProcess(handle, 1):
                raise OSError(kernel32.GetLastError(), "Failed to terminate process")
        finally:
            kernel32.CloseHandle(handle)
        return

    os.kill(pid, signal.SIGTERM)


def _running_interfaces_from_state() -> dict[str, int]:
    state = _load_interface_state()
    running: dict[str, int] = {}
    stale_interfaces: list[str] = []

    if not state or not isinstance(state, dict):
        return running

    legacy_pid = state.get("pid")
    iface_map = state.get("interfaces") or {}
    if not isinstance(iface_map, dict):
        if isinstance(legacy_pid, int) and not _is_running(legacy_pid):
            _clear_interface_state()
        return running

    for name, details in iface_map.items():
        if name not in _KNOWN_INTERFACES:
            continue
        pid = details.get("pid") if isinstance(details, dict) else None
        if not isinstance(pid, int):
            pid = legacy_pid
        if isinstance(pid, int) and _is_running(pid):
            running[name] = pid
        else:
            stale_interfaces.append(name)

    if stale_interfaces:
        _remove_interface_state(stale_interfaces)

    return running


def _is_url_reachable(url: str, *, timeout: float = 0.5) -> bool:
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=timeout):
            return True
    except (HTTPError, URLError, OSError):
        return False


def _wait_for_background_start(
    process: subprocess.Popen[bytes],
    selected: list[str],
    *,
    timeout: float = 10.0,
) -> bool:
    deadline = time.monotonic() + timeout
    saw_state = False

    while time.monotonic() < deadline:
        if process.poll() is not None:
            logger.error(
                "Background interface process exited early: pid=%s returncode=%s interfaces=%s",
                process.pid,
                process.returncode,
                ", ".join(selected),
            )
            return False

        running = _running_interfaces_from_state()
        saw_state = saw_state or all(name in running for name in selected)

        if "web" in selected:
            if saw_state and _is_url_reachable(_web_health_url()):
                return True
        elif saw_state:
            return True

        time.sleep(0.1)

    logger.warning(
        "Timed out waiting for background interface readiness: pid=%s interfaces=%s",
        process.pid,
        ", ".join(selected),
    )
    return saw_state


def _spawn_interface_process(
    selected: list[str],
    *,
    open_browser: bool = False,
) -> subprocess.Popen[bytes]:
    cmd = [
        sys.executable,
        "-m",
        "agens",
        "_run-interfaces",
        *(["--open-browser"] if open_browser and "web" in selected else []),
        *selected,
    ]
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
        )
    else:
        kwargs["start_new_session"] = True

    log_dir = get_runtime_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_name = "-".join(selected)
    log_path = log_dir / f"interfaces-{log_name}.log"

    logger.info("Spawning interface process: %s", " ".join(cmd))
    with log_path.open("ab") as log_file:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            **kwargs,
        )


def _validate_interfaces(interfaces: list[str]) -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    unknown: list[str] = []

    for arg in interfaces:
        name = arg.lower()
        if name not in VALID_INTERFACES:
            unknown.append(arg)
        elif name not in seen:
            seen.add(name)
            selected.append(name)

    if unknown:
        error_console.print(
            f"[red]Error:[/red] Unknown interface(s): {', '.join(unknown)}"
        )
        error_console.print(f"Valid options: {', '.join(sorted(VALID_INTERFACES))}")
        raise typer.Exit(code=1)

    return selected


def _build_starter(
    name: str,
    agent,
    *,
    tui_session_id: str | None = None,
    open_browser: bool = False,
):  # type: ignore[return]
    """Return the start_<name>(agent) coroutine for the requested interface."""
    match name:
        case "web":
            from interfaces.web.app import start_web
            return start_web(agent, open_browser=open_browser)
        case "telegram":
            from interfaces.telegram.bot import start_telegram
            return start_telegram(agent)
        case "tui":
            from interfaces.tui.runner import start_tui
            return start_tui(agent, session_id=tui_session_id)


async def _run_interfaces(
    selected: list[str],
    *,
    tui_session_id: str | None = None,
    open_browser: bool = False,
) -> None:
    if "tui" in selected and len(selected) > 1:
        others = [s for s in selected if s != "tui"]
        error_console.print(
            "[yellow]Warning:[/yellow] TUI is running alongside "
            f"{', '.join(others)}. Terminal output may interleave."
        )

    from agent.factory import build_agent
    from db.database import async_session
    from interfaces.dormant_agent import build_dormant_agent

    await bootstrap_database()

    async with async_session() as db:
        no_api_keys = not await has_any_api_keys(APIKeyRepository(db))

    logger.info("Building agent…")
    if no_api_keys:
        agent = build_dormant_agent()
        agent.no_api_keys_at_startup = True
    else:
        try:
            async with async_session() as db:
                agent = await build_agent(db)
            agent.no_api_keys_at_startup = False
        except (RuntimeError, LLMUnavailableError) as exc:
            logger.warning("Agent started without a usable key: %s", exc)
            agent = build_dormant_agent()
            agent.no_api_keys_at_startup = False
    logger.info("Agent ready. Starting interface(s): %s", ", ".join(selected))

    _write_interface_state(selected)

    shutdown_event = asyncio.Event()

    def request_shutdown(source: str = "unknown") -> None:
        logger.info("Shutdown requested from %s", source)
        shutdown_event.set()

    agent.request_shutdown = request_shutdown

    starters: list[asyncio.Task[None]] = []
    for name in selected:
        starter = _build_starter(
            name,
            agent,
            tui_session_id=tui_session_id if name == "tui" else None,
            open_browser=open_browser and name == "web",
        )
        if starter is None:
            raise ValueError(f"Unsupported interface: {name}")
        starters.append(asyncio.create_task(starter, name=f"{name}-interface"))

    try:
        interfaces = asyncio.gather(*starters)
        shutdown_waiter = asyncio.create_task(shutdown_event.wait(), name="shutdown-waiter")
        done, _ = await asyncio.wait(
            {interfaces, shutdown_waiter},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if shutdown_waiter in done:
            # Let interfaces (especially web/uvicorn) exit cleanly before forcing cancellation.
            try:
                await asyncio.wait_for(interfaces, timeout=5)
            except TimeoutError:
                interfaces.cancel()
                await asyncio.gather(interfaces, return_exceptions=True)
        else:
            shutdown_waiter.cancel()
            await asyncio.gather(shutdown_waiter, return_exceptions=True)
            await interfaces
    finally:
        _remove_interface_state(selected, pid=os.getpid())


def _run_interface_command(interfaces: list[str], *, tui_session_id: str | None = None) -> None:
    bootstrap_runtime()

    if not interfaces:
        error_console.print("[red]Error:[/red] No interfaces specified.")
        raise typer.Exit(code=1)

    selected = _validate_interfaces(interfaces)
    if not selected:
        error_console.print("[red]Error:[/red] No valid interfaces specified.")
        raise typer.Exit(code=1)

    foreground = [name for name in selected if name in _INTERACTIVE_INTERFACES]
    background = [name for name in selected if name not in _INTERACTIVE_INTERFACES]
    running = _running_interfaces_from_state()
    already_running = [name for name in background if name in running]
    if already_running:
        for name in already_running:
            console.print(
                f"{name} interface is already running "
                f"(PID {running[name]}): {_interface_details(name)}"
            )
        background = [name for name in background if name not in running]

    if background:
        if "telegram" in background:
            from config.config_manager import ConfigManager
            from rich.panel import Panel
            config = ConfigManager().load_config()
            if not config.telegram_token:
                error_console.print(Panel(
                    "[bold red]Telegram Token Not Set[/bold red]\n\n"
                    "You need to set up your Telegram bot token to use the Telegram interface.\n\n"
                    "If you are not sure how to configure it manually, you can start the TUI or Web session\n"
                    "and simply tell the agent your token:\n\n"
                    "[green]\"Here is my Telegram API key: <your_token>. Please set it up for me.\"[/green]\n\n"
                    "The agent will automatically configure the settings for you.",
                    title="Configuration Error",
                    border_style="red"
                ))
                background.remove("telegram")
                if "telegram" in selected:
                    selected.remove("telegram")
        
        if background:
            try:
                process = _spawn_interface_process(
                    background,
                    open_browser=selected == ["web"],
                )
            except OSError as exc:
                error_console.print(f"[red]Error:[/red] Failed to launch interface process: {exc}")
                raise typer.Exit(code=1)

            if not _wait_for_background_start(process, background):
                error_console.print(
                    "[red]Error:[/red] Interface process exited before it became ready. "
                    f"See {get_runtime_root() / 'logs'} for startup logs."
                )
                raise typer.Exit(code=1)

            console.print(
                f"Started {', '.join(background)} interface(s) in the background "
                f"(PID {process.pid})."
            )

    if foreground:
        try:
            _run(_run_interfaces(foreground, tui_session_id=tui_session_id))
        except KeyboardInterrupt:
            console.print("\nShutting down. Goodbye.")


@app.command("_run-interfaces", hidden=True)
def run_interfaces_process(
    interfaces: list[str] = typer.Argument(..., help="Interfaces to launch."),
    open_browser: bool = typer.Option(
        False,
        "--open-browser",
        help="Open the web interface once it is reachable.",
        hidden=True,
    ),
) -> None:
    """Internal blocking runner used by detached interface processes."""
    selected = _validate_interfaces(interfaces)
    try:
        _run(_run_interfaces(selected, open_browser=open_browser))
    except KeyboardInterrupt:
        console.print("\nShutting down. Goodbye.")


# ---------------------------------------------------------------------------
# Interface launch commands
# ---------------------------------------------------------------------------


@app.command("start")
def start_interfaces(
    interfaces: list[str] = typer.Argument(..., help="Interfaces to launch."),
    tui_session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume a TUI session by ID.",
    ),
) -> None:
    """Start one or more interfaces."""
    _run_interface_command(interfaces, tui_session_id=tui_session_id)


@app.command("web")
def start_web_interface() -> None:
    """Start the web interface."""
    _run_interface_command(["web"])


@telegram_app.callback(invoke_without_command=True)
def telegram(
    ctx: typer.Context,
) -> None:
    """Start the Telegram interface, or manage Telegram integration."""
    if ctx.invoked_subcommand is None:
        _run_interface_command(["telegram"])


def start_telegram_interface() -> None:
    """Start the Telegram interface."""
    _run_interface_command(["telegram"])


@app.command("tui")
def start_tui_interface(
    session_id: str | None = typer.Option(
        None,
        "--session",
        "-s",
        help="Resume a TUI session by ID.",
    )
) -> None:
    """Start the terminal UI interface."""
    _run_interface_command(["tui"], tui_session_id=session_id)


@app.command("chat")
@_with_database
def chat_command(
    message: str = typer.Argument(..., help="Message to send to the assistant."),
    model: str | None = typer.Option(None, "--model", "-m", help="Model to use."),
) -> None:
    """Send one message from the CLI."""
    async def _chat_once() -> tuple[int, str]:
        from agent.agent import Channel
        from agent.factory import build_agent
        from db import repository as session_repo
        from interfaces.dormant_agent import build_dormant_agent

        async with async_session() as db:
            repo = APIKeyRepository(db)
            if not await has_any_api_keys(repo):
                return 1, NO_API_KEYS_CLI_MESSAGE

        try:
            async with async_session() as db:
                agent = await build_agent(db)
        except (RuntimeError, LLMUnavailableError):
            agent = build_dormant_agent()

        async with async_session() as db:
            session = await session_repo.insert_session(db, title=message[:60])

        parts: list[str] = []
        async for event in agent.chat(message, session.id, channel=Channel.WEB, model=model):
            if event.type == "token" and event.content:
                parts.append(event.content)
            elif event.type == "error" and event.error:
                return 1, user_key_unavailable_message(event.error)

        return 0, "".join(parts).strip()

    try:
        code, output = _run(_chat_once())
    except RuntimeError as exc:
        console.print(user_key_unavailable_message(str(exc)))
        raise typer.Exit(code=1)
    except Exception as exc:
        error_console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    if output:
        console.print(output)
    raise typer.Exit(code=code)


# ---------------------------------------------------------------------------
# API key commands
# ---------------------------------------------------------------------------


@apikey_app.command("add")
@_with_database
def apikey_add(
    label: str = typer.Argument(..., help="Human-friendly label for the key."),
    provider: str = typer.Argument(..., help="Provider name (e.g. gemini)."),
    api_key: str = typer.Argument(..., help="The raw API key value."),
) -> None:
    """Add a new API key."""
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
@_with_database
def apikey_list() -> None:
    """List stored API keys."""
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
        console.print("No API keys found. Add one with: agens apikey add")
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
@_with_database
def apikey_remove(
    label: str = typer.Argument(..., help="Label of the key to remove."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Remove an API key by label."""
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
@_with_database
def apikey_toggle(
    label: str = typer.Argument(..., help="Label of the key to toggle."),
) -> None:
    """Toggle an API key between active and inactive."""
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
@_with_database
def safety_toggle() -> None:
    """Toggle safety mode on or off."""
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
@_with_database
def safety_status() -> None:
    """Show the current safety mode state."""
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
    bootstrap_runtime()

    state = _load_interface_state()
    running_pids: dict[str, int] = {}
    stale_state = False

    if state and isinstance(state, dict):
        legacy_pid = state.get("pid")
        iface_map = state.get("interfaces") or {}
        if isinstance(iface_map, dict):
            stale_interfaces: list[str] = []
            for name, details in iface_map.items():
                if name not in _KNOWN_INTERFACES:
                    continue
                pid = details.get("pid") if isinstance(details, dict) else None
                if not isinstance(pid, int):
                    pid = legacy_pid
                if isinstance(pid, int) and _is_running(pid):
                    running_pids[name] = pid
                else:
                    stale_state = True
                    stale_interfaces.append(name)

            if stale_interfaces:
                _remove_interface_state(stale_interfaces)
        elif isinstance(legacy_pid, int) and not _is_running(legacy_pid):
            stale_state = True
            _clear_interface_state()

    table = Table(title="Interfaces", header_style="bold")
    table.add_column("Interface")
    table.add_column("Status")
    table.add_column("PID")
    table.add_column("Details")

    for name in _KNOWN_INTERFACES:
        pid = running_pids.get(name)
        is_running = pid is not None
        status_text = Text("running", style="green") if is_running else Text("stopped", style="dim")
        pid_text = str(pid) if pid is not None else "-"
        details = _interface_details(name) if is_running else "not running"
        if stale_state and not running_pids:
            details = "stale runtime state"
        table.add_row(name, status_text, pid_text, details)

    console.print(table)

    if not running_pids:
        console.print("No interfaces running. Start one with: agens web")


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


@app.command("shutdown")
def shutdown(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Gracefully shut down the assistant."""
    bootstrap_runtime()

    if not yes and not typer.confirm("Shut down the assistant and all interfaces?", default=False):
        console.print("Cancelled.")
        raise typer.Exit(code=0)

    state = _load_interface_state()
    if not state or "pid" not in state:
        error_console.print("[red]Error:[/red] No running assistant process found.")
        raise typer.Exit(code=1)

    legacy_pid = state.get("pid")
    iface_map = state.get("interfaces") or {}
    pid_by_interface: dict[str, int] = {}
    stale_interfaces: list[str] = []

    if isinstance(iface_map, dict):
        for name, details in iface_map.items():
            if name not in _KNOWN_INTERFACES:
                continue
            pid = details.get("pid") if isinstance(details, dict) else None
            if not isinstance(pid, int):
                pid = legacy_pid
            if isinstance(pid, int) and _is_running(pid):
                pid_by_interface[name] = pid
            else:
                stale_interfaces.append(name)
    elif isinstance(legacy_pid, int) and _is_running(legacy_pid):
        pid_by_interface = {name: legacy_pid for name in _KNOWN_INTERFACES}

    if stale_interfaces:
        _remove_interface_state(stale_interfaces)

    if not pid_by_interface:
        _clear_interface_state()
        error_console.print("[red]Error:[/red] No running assistant process found.")
        raise typer.Exit(code=1)

    gracefully_stopped_pids: set[int] = set()
    if "web" in pid_by_interface and _request_web_shutdown():
        gracefully_stopped_pids.add(pid_by_interface["web"])
        console.print("Shutdown requested via web interface.")

    for pid in sorted(set(pid_by_interface.values()) - gracefully_stopped_pids):
        try:
            _terminate_process(pid)
        except OSError as exc:
            error_console.print(f"[red]Error:[/red] {exc}")
            raise typer.Exit(code=1)

    _clear_interface_state()
    console.print("Shutdown signal sent.")


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


@telegram_app.command("set-token")
def telegram_set_token(
    token: str = typer.Argument(..., help="Telegram bot token."),
) -> None:
    """Set the Telegram bot token."""
    bootstrap_runtime()

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


def cli() -> None:
    """Console entry point for the unified CLI."""
    app()


if __name__ == "__main__":
    cli()
