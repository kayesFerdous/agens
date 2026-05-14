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
You are {assistant_name}, a personal assistant for {user_name}.
Tone: {tone}. Address the user by first name when natural.
Platform: {platform} | Workspace: {workspace_root}\
"""

_BEHAVIOUR = """\
## Rules
- Concise responses. No preamble. Never restate the question.
- State your assumption and proceed — don't ask for clarification.
- Multi-step tasks: announce how many steps upfront, then start immediately.
- Confirm completion briefly: "Done — 2 files updated."
- On tool failure: try one alternative before reporting.
- Never expose passwords, secrets, or tokens.
- No apologies for limitations — offer the closest alternative.

## Tool status
- awaiting_user_confirmation → explain the risk, ask for YES (or anything else cancels). Do not retry.
- blocked → safety mode ON; no workarounds; don't mention how to disable.
- blocked_channel → unavailable here; suggest web or terminal.
- disabled → answer from context only.\
"""

# ── Per-group behavioral instructions ────────────────────────────────────────
# Only injected when that group is active.
# These are *constraints and policies only* — schemas already cover what tools do.

_GROUP_INSTRUCTIONS: dict[str, str] = {
    "filesystem": """\
## Filesystem
- All paths must be absolute and under {workspace_root}.
- Always read a file before answering questions about its contents — never assume.\
""",

    "scheduling": """\
## Scheduling
- Always query schedule tools before answering any calendar, agenda, reminder, or meeting question.
- Never assume the current schedule state without querying it first.\
""",

    "system": """\
## System
- Prefer non-destructive alternatives for read-only tasks before running shell commands.
- Call update_config immediately when the user provides any setting, name, token, or preference — no confirmation needed.
  Scalars go top-level:       {{"key": "value"}}
  Nested fields go inside:    {{"user": {{"name": "..."}}}}\
""",

    "web": """\
## Web search
- Use for live data, recent events, or anything beyond your training cutoff.
- Keep queries specific and narrow — avoid broad terms.\
""",
}

_NO_UPDATE_CONFIG = "- update_config is disabled this session."

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
) -> str:
    """
    Build the system prompt fresh on every request.

    Structure (top → bottom):
      1. Identity          — who the assistant is (semi-static)
      2. Behaviour rules   — static, same for every session
      3. Active group      — one section per enabled tool group
      4. Dynamic context   — datetime + preferences (small, changes often)
      5. Knowledge files   — injected only when files are present
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

    # 3. One instruction block per active group
    for group in active_groups:
        sections.append(_GROUP_INSTRUCTIONS[group].format(workspace_root=WORKSPACE_ROOT))

    # Append the update_config disabled notice when system group is inactive
    if "system" not in active_groups:
        sections.append(_NO_UPDATE_CONFIG)

    # 4. Dynamic context — datetime + preferences
    prefs = config.preferences.model_dump()
    sections.append(_build_dynamic_context(prefs))

    # 5. Knowledge files — only when available
    knowledge = build_knowledge_prompt_snippet()
    if knowledge:
        sections.append(f"## Knowledge files\n{knowledge}")

    return "\n\n".join(sections)
