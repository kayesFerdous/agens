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
import sys
from typing import Any, Coroutine

from config.settings import settings
from config.runtime import initialize_runtime
from config.logging import get_logger, setup_logging


initialize_runtime()

setup_logging(settings.LOG_LEVEL)
logger = get_logger(__name__)

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

    starters: list[Coroutine[Any, Any, None]] = []
    for name in selected:
        starter = _build_starter(name, agent)
        if starter is None:
            raise ValueError(f"Unsupported interface: {name}")
        starters.append(starter)

    if len(starters) == 1:
        await starters[0]
    else:
        await asyncio.gather(*starters)


def cli() -> None:
    """Sync entry point for console scripts."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down. Goodbye.")


if __name__ == "__main__":
    cli()
