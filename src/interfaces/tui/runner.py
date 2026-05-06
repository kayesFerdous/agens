# Run instructions:
#   uv run python -m src.main --interface tui
#   Requirements: textual>=0.60.0
#
# If you see a blank screen: check that ChatView has height: 1fr in CSS.
# If geometry text appears on screen, find scroll calls whose return value is rendered.
from __future__ import annotations

from .app import AssistantTUI


async def run_tui(agent) -> None:
    app = AssistantTUI(agent=agent)
    await app.run_async()


async def start_tui(agent) -> None:
    await run_tui(agent)
