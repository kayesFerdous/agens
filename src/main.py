"""
main.py — unified launcher for the AI assistant.

Usage:
    python main.py web                  # web interface only
    python main.py telegram             # telegram bot only
    python main.py tui                  # terminal UI only
    python main.py web telegram         # web + telegram concurrently
    python main.py web telegram tui     # all three concurrently
"""
from __future__ import annotations
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from config.settings import settings
from config.runtime import get_runtime_root, initialize_runtime
from config.logging import get_logger, setup_logging


initialize_runtime()

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

_INTERFACE_STATE_FILE = get_runtime_root() / "interfaces.json"


def _write_interface_state(selected: list[str]) -> None:
    data = {
        "pid": os.getpid(),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "interfaces": {name: {"status": "running"} for name in selected},
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




#TODO:
#add the following commands:
# ---- API key commands ----  
# - user should be able to add api_key (label, provider, key)
# - user should be able to list api_keys
# - user should be able to remove api_key by label
# - user should be able to toggle api_key active/inactive by label
# ---- Safety Mode Command ----  
# - user should be able to toggle safety mode on/off
# - user should be able to see current safety mode status
# ---- Other Commands ----
# - user should be able to see which interfaces are currently running
# - user should be able to gracefully shutdown the assistant from any interface
# - user should be able to add telegram token via command


VALID_INTERFACES = {"web", "telegram", "tui"}

USAGE = """\
Usage: python main.py <interface> [<interface> ...]
    python -m main --interface <interface> [<interface> ...]
    vela <interface> [<interface> ...]

Available interfaces:
  web        FastAPI + uvicorn REST/SSE server
  telegram   Telegram bot (webhook or polling)
  tui        Interactive terminal UI

Examples:
  python main.py web
    python -m main --interface web
    vela web
  python main.py telegram
  python main.py web telegram tui
"""


def _parse_args(argv: list[str]) -> list[str]:
    """Validate and deduplicate interface names, preserving order."""
    if argv[:1] == ["--interface"]:
        argv = argv[1:]

    if not argv:
        print(USAGE, end="")
        sys.exit(0)

    seen: set[str] = set()
    selected: list[str] = []
    unknown: list[str] = []

    for arg in argv:
        name = arg.lower()
        if name not in VALID_INTERFACES:
            unknown.append(arg)
        elif name not in seen:
            seen.add(name)
            selected.append(name)

    if unknown:
        print(f"[error] Unknown interface(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"Valid options: {', '.join(sorted(VALID_INTERFACES))}", file=sys.stderr)
        sys.exit(1)

    return selected


def _build_starter(name: str, agent):  # type: ignore[return]
    """Return the start_<name>(agent) coroutine for the requested interface."""
    match name:
        case "web":
            from interfaces.web.app import start_web
            return start_web(agent)
        case "telegram":
            from interfaces.telegram.bot import start_telegram
            return start_telegram(agent)
        case "tui":
            from interfaces.tui.runner import start_tui
            return start_tui(agent)


async def main() -> None:
    selected = _parse_args(sys.argv[1:])

    # Warn early if tui is mixed with other interfaces (stdout will interleave).
    if "tui" in selected and len(selected) > 1:
        others = [s for s in selected if s != "tui"]
        print(
            f"[warning] TUI is running alongside {', '.join(others)}. "
            "Terminal output may interleave.",
            file=sys.stderr,
        )

    # Build the agent exactly once — shared across all interfaces.
    from agent.factory import build_agent
    from db.database import async_session

    logger.info("Building agent…")
    async with async_session() as db:
        agent = await build_agent(db)
    logger.info("Agent ready. Starting interface(s): %s", ", ".join(selected))

    _write_interface_state(selected)

    shutdown_event = asyncio.Event()

    def request_shutdown(source: str = "unknown") -> None:
        logger.info("Shutdown requested from %s", source)
        shutdown_event.set()

    agent.request_shutdown = request_shutdown

    starters: list[asyncio.Task[None]] = []
    for name in selected:
        starter = _build_starter(name, agent)
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
            interfaces.cancel()
            await asyncio.gather(interfaces, return_exceptions=True)
        else:
            shutdown_waiter.cancel()
            await asyncio.gather(shutdown_waiter, return_exceptions=True)
            await interfaces
    finally:
        _clear_interface_state()


def cli() -> None:
    """Sync entry point for console scripts."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye.")


if __name__ == "__main__":
    cli()
