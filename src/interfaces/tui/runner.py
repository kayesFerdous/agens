# Run via: uv run python -m src.main --interface tui
# Requires: textual>=0.60.0
from __future__ import annotations

from .app import AssistantTUI


async def run_tui(agent) -> None:
    app = AssistantTUI(agent=agent)
    await app.run_async()


async def start_tui(agent) -> None:
    """Backward-compatible entrypoint used by src.main."""
    await run_tui(agent)
