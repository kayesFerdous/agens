from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import AssistantTUI


COMMANDS = {
    "/help": "Show this help panel",
    "/clear": "Clear the visible chat",
    "/exit": "Exit the TUI",
    "/quit": "Exit the TUI",
    "/model": "Show the active model name",
    "/tokens": "Show the session token count",
    "?": "Show this help panel",
}


def is_command(text: str) -> bool:
    stripped = text.strip()
    return stripped == "?" or stripped.startswith("/")


async def handle_command(text: str, app: "AssistantTUI") -> None:
    command = text.strip().split(maxsplit=1)[0].lower()
    if command == "?":
        command = "/help"

    if command == "/help":
        lines = ["◆ System", "", "**Commands**"]
        lines.extend(f"- `{name}` - {description}" for name, description in COMMANDS.items())
        await app.add_system_message("\n".join(lines))
    elif command == "/clear":
        await app.clear_chat()
        await app.add_system_message("◆ System\n\nChat cleared.")
    elif command in {"/exit", "/quit"}:
        app.exit()
    elif command == "/model":
        await app.add_system_message(f"◆ System\n\nCurrent model: `{app.model_name}`")
    elif command == "/tokens":
        await app.add_system_message(f"◆ System\n\nSession tokens: `{app.token_count}`")
    else:
        await app.add_system_message(f"◆ System\n\nUnknown command: `{command}`. Type `?` for help.")
