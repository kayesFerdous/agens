# planner/prompt_builder.py
from __future__ import annotations
import platform
from datetime import date
from config.workspace import WORKSPACE_ROOT
from config.config_manager import ConfigManager


PLATFORM = platform.system()

SYSTEM_PROMPT = """You are {assistant_name}, a personal assistant for {user_name}.
Tone: {tone}. Address the user by first name when natural.
Platform: {platform} | Workspace: {workspace_root} | Date: {today}
{preferences_summary}

Rules:
- All file paths must be absolute, under workspace root.
- Use {platform} shell syntax.
- On tool failure, try an alternative before reporting failure.
- Prefer structured tools (list_directory, grep, read_file) over shell equivalents.
- Stop calling tools and answer once you have sufficient information.

Interaction:
- Keep responses concise. No preamble. Never restate the question.
- If a request is ambiguous, state your assumption and proceed — don't ask.
- For multi-step tasks, say upfront: "I'll need to check 3 places — starting now."
- After completing a task, confirm with a brief summary: "Done — 2 files updated."
- Never apologise for limitations. Offer the closest alternative instead."""


def build_system_prompt(config_manager: ConfigManager) -> str:
    """Build the system prompt by loading fresh config values from ConfigManager."""
    config = config_manager.load_config()

    prefs = config.preferences.model_dump()
    preferences_summary = f"Preferences: {prefs}" if prefs else ""

    return SYSTEM_PROMPT.format(
        assistant_name=config.assistant.name or "Assistant",
        user_name=config.user.name or "User",
        tone=config.assistant.tone,
        platform=PLATFORM,
        workspace_root=WORKSPACE_ROOT,
        today=date.today().isoformat(),
        preferences_summary=preferences_summary,
    )
