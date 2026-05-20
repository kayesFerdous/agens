# Run instructions:
#   uv run python -m agens tui
#   agens tui
#   Requirements: textual>=0.60.0
#
# If you see a blank screen: check that ChatView has height: 1fr in CSS.
# If geometry text appears on screen, find scroll calls whose return value is rendered.
from __future__ import annotations

from config.logging import setup_logging
from .app import AssistantTUI


async def run_tui(agent, session_id: str | None = None) -> None:
    # Reconfigure logging to write to agens.log instead of sys.stderr
    # to avoid corrupting the Textual terminal display.
    setup_logging(force=True, is_tui=True)

    app = AssistantTUI(agent=agent, session_id=session_id)
    await app.run_async()
    if app.session_id:
        print(f"Resume this session with: agens tui -s {app.session_id}")


async def start_tui(agent, session_id: str | None = None) -> None:
    await run_tui(agent, session_id=session_id)
