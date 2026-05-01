# interfaces/tui/runner.py — interactive terminal adapter: start_tui(agent)
from __future__ import annotations

import asyncio
import sys

from agent.agent import Agent
from config.logging import get_logger
from db.database import async_session
from db import repository as session_repo

logger = get_logger(__name__)

_EXIT_COMMANDS = frozenset({"exit", "quit", "q"})


async def start_tui(agent: Agent) -> None:
    """Run an interactive terminal session using the shared agent."""
    loop = asyncio.get_running_loop()

    # Create a DB session for this TUI run.
    async with async_session() as db:
        session = await session_repo.insert_session(db, title="TUI Session")
        session_id = session.id

    print(f"\n[Assistant TUI — session {session_id}]")
    print(f"[Type your message and press Enter. '{'/'.join(sorted(_EXIT_COMMANDS))}' to quit.]\n")

    while True:
        # Non-blocking read so we don't block the event loop while other
        # interfaces (web, telegram) are running concurrently.
        try:
            raw = await loop.run_in_executor(None, sys.stdin.readline)
        except EOFError:
            break

        user_text = raw.strip()
        if not user_text:
            continue
        if user_text.lower() in _EXIT_COMMANDS:
            print("\nGoodbye.")
            break

        print("…", flush=True)

        try:
            answer_parts: list[str] = []
            async for event in agent.chat(user_text, session_id):
                if event.type == "token" and event.content:
                    # Stream tokens to stdout as they arrive.
                    print(event.content, end="", flush=True)
                    answer_parts.append(event.content)
                elif event.type == "status" and event.message:
                    print(f"\n[{event.message}]", flush=True)
                elif event.type == "error" and event.error:
                    print(f"\n⚠️  Error: {event.error}", flush=True)
                    break
                elif event.type == "done" and event.usage:
                    u = event.usage
                    print(
                        f"\n\n[tokens — prompt: {u.prompt_tokens}  "
                        f"completion: {u.completion_tokens}  "
                        f"total: {u.total_tokens}]",
                        flush=True,
                    )

            # Ensure the prompt appears on a fresh line after streamed tokens.
            if answer_parts:
                print()

        except Exception as e:
            logger.exception("Unhandled error in TUI loop: %s", e)
            print(f"\n⚠️  Unexpected error: {e}")

        print()  # blank line before the next prompt
