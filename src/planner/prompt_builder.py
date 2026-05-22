# planner/prompt_builder.py
from __future__ import annotations

import platform
from datetime import datetime

from config.runtime import build_knowledge_prompt_snippet
from config.workspace import WORKSPACE_ROOT
from config.config_manager import ConfigManager
from core.tool_groups import TOOL_GROUPS


PLATFORM = platform.system()


# ── Static sections ─────────────────────────────────

_IDENTITY = """\
You are {assistant_name}, a {tone} assistant for {user_name}.
OS: {platform} | Workspace: {workspace_root}\
"""

_BEHAVIOUR = """\
## Rules
- Be concise. No preamble or restating the question.
- Assume and proceed instead of asking questions.
- For multi-step tasks, list step count, then begin.
- Briefly confirm completion (e.g., 'Done — 2 files updated').
- If a tool fails, try one alternative first.
- Never expose secrets or tokens.
- Don't apologize for limitations; offer alternatives.
- Act only on the latest message; never repeat actions already in chat history.
- When a task requires a disabled capability, do not guess. State it is disabled, tell them how to enable it in settings, and supply exact manual commands/steps they can execute themselves.

## Tool status
- awaiting_user_confirmation: Explain risk, ask for YES (other inputs cancel). Do not retry.
- blocked: Safety mode ON. No workarounds; don't mention disabling.
- blocked_channel: Unavailable here. Suggest Web or TUI/terminal.
- disabled: Explain that the capability is disabled, suggest how to enable it, and offer manual alternatives.\
"""

# ── Sudo policy (channel-aware + safety_mode-aware) ──────────────────────────

def _sudo_policy(safety_mode: bool, channel: str) -> str:
    if safety_mode:
        return (
            "## Privileged Commands\n"
            "- Sudo BLOCKED (Safety Mode ON). Refuse privileged commands: 'Sudo is disabled while safety mode is on.'"
        )
    if channel == "tui":
        return (
            "## Privileged Commands\n"
            "- Sudo ALLOWED. Prefer non-privileged options. Sudo only when required. Never expose/log password."
        )
    return (
        "## Privileged Commands\n"
        "- Sudo BLOCKED (Web/Telegram). Direct user to TUI: 'Sudo commands can only be run from the TUI. Launch it with `agens tui`.'"
    )

# ── Per-group behavioral instructions ────────────────────────────────────────
# Only injected when that group is active.
# These are *constraints and policies only* — schemas already cover what tools do.

_GROUP_INSTRUCTIONS: dict[str, str] = {
    "filesystem": """\
## Filesystem
- Paths must be absolute and under {workspace_root}.
- Read files to answer questions about their content; do not assume.\
""",

    "scheduling": """\
## Scheduling
- Query schedule tools before answering calendar/event questions; never assume.\
""",

    "system": """\
## System
- Prefer structured tools over shell commands for read-only tasks.
- Call update_config when user provides setting/fact/memory updates (no confirmation needed):
  Scalars: {{"key": "value"}}
  Memories: {{"user": {{"memories": {{"hobby": "reading"}}}}}}
  Forget: {{"user": {{"memories": {{"hobby": null}}}}}}\
""",

    "web": """\
## Web search
- Use web_search for current info/events. Keep queries narrow.
- Use web_fetch only when web_search snippets lack critical detail.\
""",
}

_NO_UPDATE_CONFIG = "- update_config disabled."

_DISABLED_CAPABILITY_INFO: dict[str, str] = {
    "filesystem": "- Filesystem (files/directories): Disabled. Suggest enabling in settings only if unavoidable; otherwise, provide manual instructions/edits.",
    "scheduling": "- Scheduling/Calendar: Disabled. Suggest enabling in settings only if unavoidable; otherwise, answer using available details.",
    "system": "- System/Terminal/UpdateUserConfig: Disabled. Suggest enabling in settings only if unavoidable; otherwise, supply exact commands for user to run.",
    "web": "- Web Search: Disabled. Suggest enabling in settings only if unavoidable; otherwise, ask user for the source text.",
}

# ── Dynamic section (changes every request) ───────────────────────────────────

_DYNAMIC_CONTEXT = """\
DateTime: {now}{preferences}\
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _active_groups(tool_names: set[str]) -> list[str]:
    """Return groups that have at least one tool present in tool_names."""
    return [
        group
        for group, tools in TOOL_GROUPS.items()
        if tool_names & set(tools)
    ]


def _build_dynamic_context(preferences: dict) -> str:
    pref_line = f"\nPreferences: {preferences}" if preferences else ""
    return _DYNAMIC_CONTEXT.format(
        now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        preferences=pref_line,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def build_system_prompt(
    config_manager: ConfigManager,
    tool_schemas: list[dict] | None = None,
    safety_mode: bool = True,
    channel: str = "web",  # "tui" | "web" | "telegram"
) -> str:
    """
    Build the system prompt fresh on every request.

    Structure (top → bottom):
      1. Identity          — who the assistant is (semi-static)
      2. Behaviour rules   — static, same for every session
      3. Sudo policy       — dynamic: channel + safety_mode aware
      4. Active group      — one section per enabled tool group
      5. Dynamic context   — datetime + preferences (small, changes often)
      6. Knowledge files   — injected only when files are present
    """
    config = config_manager.load_config()
    tool_names: set[str] = {str(t["name"]) for t in (tool_schemas or [])}
    active_groups = _active_groups(tool_names)

    sections: list[str] = []

    # 1. Identity
    sections.append(_IDENTITY.format(
        assistant_name=config.assistant.name or "Assistant",
        user_name=config.user.name or "User",
        tone=config.assistant.tone,
        platform=PLATFORM,
        workspace_root=WORKSPACE_ROOT,
    ))

    # 2. Behaviour (static)
    sections.append(_BEHAVIOUR)

    # 3. Sudo policy — channel + safety_mode aware (single line, minimal tokens)
    sections.append(_sudo_policy(safety_mode, channel))

    # 4. One instruction block per active group
    for group in active_groups:
        sections.append(_GROUP_INSTRUCTIONS[group].format(workspace_root=WORKSPACE_ROOT))

    # Inactive/disabled capabilities
    inactive_groups = [g for g in TOOL_GROUPS if g not in active_groups]
    if inactive_groups:
        disabled_sec = ["## Disabled Capabilities"]
        for group in inactive_groups:
            disabled_sec.append(_DISABLED_CAPABILITY_INFO[group])
        sections.append("\n".join(disabled_sec))

    # Append the update_config disabled notice when system group is inactive
    if "system" not in active_groups:
        sections.append(_NO_UPDATE_CONFIG)

    # 5. Dynamic context — datetime + preferences + memories
    prefs = config.preferences.model_dump()
    sections.append(_build_dynamic_context(prefs))
    if config.user.memories:
        mem = ", ".join(f"{k}: {v}" for k, v in config.user.memories.items())
        sections.append(f"Remembered about user: {mem}")

    # 6. Knowledge files — only when available
    knowledge = build_knowledge_prompt_snippet()
    if knowledge:
        sections.append(f"## Knowledge files\n{knowledge}")

    return "\n\n".join(sections)
