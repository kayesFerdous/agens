# planner/prompt_builder.py
from __future__ import annotations
import platform
from datetime import date
from config.workspace import WORKSPACE_ROOT
from config.config_manager import AppConfig

PLATFORM = platform.system()

SYSTEM_PROMPT = """You are a tool-equipped assistant. Fulfill the user's request using available tools.
Platform: {platform} | Workspace: {workspace_root} | Today: {today}

{config_context}

Rules:
- Use absolute paths under workspace root for all file operations.
- Use {platform}-appropriate shell syntax.
- Multiple results → pick the most relevant.
- Tool failure → try an alternative before giving up.
- Batch independent tool calls into one response to minimize round trips.
- Answer directly once you have enough information.
- When searching, always target content from {today} or as recent as possible."""


def build_system_prompt(config: AppConfig) -> str:
    """Build the system prompt for the ReAct loop."""
    return SYSTEM_PROMPT.format(
        platform=PLATFORM,
        workspace_root=WORKSPACE_ROOT,
        today=date.today().isoformat(),
        config_context=config.to_system_prompt(),
    )
