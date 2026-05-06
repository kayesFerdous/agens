from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import AssistantTUI


COMMANDS = {
    "/help": "Show this help message",
    "/clear": "Clear chat history",
    "/exit": "Exit the assistant",
    "/quit": "Exit the assistant",
    "/model": "Show current model",
    "/models": "Select a model interactively",
    "/tokens": "Show token count",
    "?": "Show this help message",
}


def parse_command(text: str) -> bool:
    value = text.strip()
    return value == "?" or value.startswith("/")


async def execute_command(text: str, app: "AssistantTUI") -> None:
    command = text.strip().split(maxsplit=1)[0].lower()
    chat = app.query_one("ChatView")

    if command in {"?", "/help"}:
        lines = ["[bold]Available commands:[/bold]"]
        for name, description in COMMANDS.items():
            lines.append(f"  [#cc785c]{name}[/#cc785c]  {description}")
        await chat.add_system("\n".join(lines))

    elif command == "/clear":
        await app._do_clear()

    elif command in {"/exit", "/quit"}:
        app.action_quit()

    elif command == "/model":
        model = getattr(app, "_selected_model", None) or getattr(app, "model_name", "unknown")
        await chat.add_system(f"Current model: [bold]{model}[/bold]")

    elif command == "/models":
        app.show_model_selector()

    elif command == "/tokens":
        await chat.add_system(f"Session tokens: [bold]{app.token_count}[/bold]")

    else:
        await chat.add_system(
            f"Unknown command: [red]{text}[/red]  - type [bold]?[/bold] for help"
        )


def is_command(text: str) -> bool:
    return parse_command(text)


async def handle_command(text: str, app: "AssistantTUI") -> None:
    await execute_command(text, app)
