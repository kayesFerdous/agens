from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .app import AssistantTUI


COMMANDS = {
    "/help": "Show this help message",
    "/clear": "Clear chat history",
    "/exit": "Exit the assistant",
    "/quit": "Exit the assistant",
    "/models": "Select a model interactively",
    "/tools": "Select active tool groups",
    "/keys": "List registered API keys",
    "/addkey": "Add a new API key",
    "/tokens": "Show token count",
    "?": "Show this help message",
}


def parse_command(text: str) -> bool:
    value = text.strip()
    return value == "?" or value.startswith("/")


def _resolve_command(command: str) -> tuple[str | None, list[str]]:
    value = command.strip().lower()
    if value == "?":
        return "?", []

    if value in COMMANDS:
        return value, []

    matches = [name for name in COMMANDS if name.startswith(value)]
    if not matches:
        return None, []

    if len(matches) == 1:
        return matches[0], []

    # Prefer the most specific command when one is a strict extension of others.
    # Example: /mod -> /models (while /model remains exact when fully typed).
    ranked = sorted(matches, key=len, reverse=True)
    if len(ranked[0]) > len(ranked[1]):
        return ranked[0], []

    return None, sorted(matches)


async def execute_command(text: str, app: "AssistantTUI") -> None:
    command = text.strip().split(maxsplit=1)[0].lower()
    resolved_command, ambiguous_matches = _resolve_command(command)
    chat = app.query_one("ChatView")

    if ambiguous_matches:
        options = "  ".join(ambiguous_matches)
        await chat.add_system(
            f"Ambiguous command: [#cc785c]{command}[/#cc785c]  matches: {options}"
        )
        return

    if resolved_command is None:
        await chat.add_system(
            f"Unknown command: [red]{text}[/red]  - type [bold]?[/bold] for help"
        )
        return

    if resolved_command in {"?", "/help"}:
        lines = ["[bold]Available commands:[/bold]"]
        for name, description in COMMANDS.items():
            lines.append(f"  [#cc785c]{name}[/#cc785c]  {description}")
        await chat.add_system("\n".join(lines))

    elif resolved_command == "/clear":
        await app._do_clear()

    elif resolved_command in {"/exit", "/quit"}:
        app.action_quit()


    elif resolved_command == "/models":
        app.show_model_selector()

    elif resolved_command == "/tools":
        app.show_tool_group_selector()

    elif resolved_command == "/keys":
        app.show_api_key_list()

    elif resolved_command == "/addkey":
        app.show_api_key_add()

    elif resolved_command == "/tokens":
        await chat.add_system(f"Session tokens: [bold]{app.token_count}[/bold]")


def is_command(text: str) -> bool:
    return parse_command(text)


async def handle_command(text: str, app: "AssistantTUI") -> None:
    await execute_command(text, app)
