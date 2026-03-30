# planner/prompt_builder.py
from __future__ import annotations
import platform
from config.workspace import WORKSPACE_ROOT
from config.config_manager import AppConfig

PLATFORM = platform.system()

SYSTEM_PROMPT = """You are a helpful assistant with access to tools. Use them as needed to fulfill the user's request.
Platform: {platform}
Workspace root: {workspace_root}

{config_context}

Guidelines:
- For filesystem tools: use absolute paths under the workspace root.
- For shell commands: use {platform}-appropriate syntax.
- If a tool returns multiple results, reason about which one is most relevant.
- If a tool fails, try an alternative approach before giving up.
- When you have enough information, respond with your final answer directly.
- Parallel execution: when multiple tools can run independently, call them all in a single response rather than waiting for each result before calling the next."""


def build_system_prompt(config: AppConfig) -> str:
    """Build the system prompt for the ReAct loop."""
    return SYSTEM_PROMPT.format(
        platform=PLATFORM,
        workspace_root=WORKSPACE_ROOT,
        config_context=config.to_system_prompt(),
    )
