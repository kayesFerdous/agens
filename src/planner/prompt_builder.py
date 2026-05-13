# planner/prompt_builder.py
from __future__ import annotations
import platform
from datetime import datetime
from config.runtime import build_knowledge_prompt_snippet
from config.workspace import WORKSPACE_ROOT
from config.config_manager import ConfigManager


PLATFORM = platform.system()

SYSTEM_PROMPT = """You are {assistant_name}, a personal assistant for {user_name}.
Tone: {tone}. Address the user by first name when natural.
Platform: {platform} | Workspace: {workspace_root} | DateTime: {now}
{preferences_summary}
Enabled tools: {enabled_tools}

## Knowledge Files
{knowledge_files}

{tool_instructions}

## Rules:
- Use {platform} shell syntax.
- On tool failure, try an alternative before reporting failure.
- Stop calling tools and answer once you have sufficient information.
- Tool status handling — match exactly:
  • "awaiting_user_confirmation" → explain the risk, ask user to reply "YES" or anything else to cancel. Do not re-call the tool or suggest workarounds.
  • "blocked" → safety mode is ON; command cannot run. No workarounds; don't mention how to disable.
  • "blocked_channel" → command unavailable on Telegram; suggest web or terminal. Don't mention safety mode.
  • "disabled" → the tool is disabled for this chat session; answer using enabled tools or conversation context.
- Never expose passwords, secrets, or tokens.

## Config Updates
{config_update_instructions}

Interaction:
- Keep responses concise. No preamble. Never restate the question.
- If a request is ambiguous, state your assumption and proceed — don't ask.
- For multi-step tasks, say upfront: "I'll need to check 3 places — starting now."
- After completing a task, confirm with a brief summary: "Done — 2 files updated."
- Never apologise for limitations. Offer the closest alternative instead."""


def _build_tool_instructions(tool_names: set[str]) -> str:
    lines: list[str] = []

    filesystem_tools = {"file_read", "file_write", "file_edit", "list_directory", "find", "grep"}
    schedule_tools = {"schedule_add", "schedule_list", "schedule_update", "schedule_delete"}

    if tool_names & filesystem_tools:
        lines.append("- All file paths must be absolute, under workspace root.")
        if "file_read" in tool_names:
            lines.append(
                "- Use file_read to read a knowledge file before answering questions that require it. Never assume file contents without reading them first."
            )
        if {"list_directory", "grep"} & tool_names:
            lines.append("- Prefer structured filesystem tools over shell equivalents.")

    if tool_names & schedule_tools:
        lines.append(
            "- For schedule, calendar, agenda, meeting, event, appointment, reminder, or \"what do I have\" requests, use schedule tools before answering."
        )

    if not lines:
        return "No tools are enabled for this chat session. Answer from conversation context only."

    return "\n".join(lines)


def _build_config_update_instructions(tool_names: set[str]) -> str:
    if "update_config" not in tool_names:
        return "- The update_config tool is disabled for this chat session."

    return "\n".join(
        [
            "- If the user provides any setting, token, name, or preference — call update_config immediately, no confirmation needed.",
            '- Scalars (e.g. telegram_token) go top-level: {"telegram_token": "..."}',
            '- Nested fields go inside their object: {"user": {"name": "..."}}.',
        ]
    )


def build_system_prompt(config_manager: ConfigManager, tool_schemas: list[dict] | None = None) -> str:
    """Build the system prompt by loading fresh config values from ConfigManager."""
    config = config_manager.load_config()

    prefs = config.preferences.model_dump()
    preferences_summary = f"Preferences: {prefs}" if prefs else ""
    tool_names = {str(tool["name"]) for tool in tool_schemas or []}
    enabled_tools = ", ".join(sorted(tool_names)) if tool_names else "none"

    return SYSTEM_PROMPT.format(
        assistant_name=config.assistant.name or "Assistant",
        user_name=config.user.name or "User",
        tone=config.assistant.tone,
        platform=PLATFORM,
        workspace_root=WORKSPACE_ROOT,
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        preferences_summary=preferences_summary,
        knowledge_files=build_knowledge_prompt_snippet(),
        enabled_tools=enabled_tools,
        tool_instructions=_build_tool_instructions(tool_names),
        config_update_instructions=_build_config_update_instructions(tool_names),
    )
