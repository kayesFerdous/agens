# planner/prompt_builder.py
from __future__ import annotations

SYSTEM_PROMPT = """You are a planning agent for a file and shell automation assistant.
Given a user request, produce a JSON array of steps. Each step is an object with:
  - "tool": one of {tool_names}
  - "arguments": a dict of keyword arguments for that tool

Rules:
- Maximum 10 steps.
- Use only the tools listed above.
- Output ONLY the JSON array, no markdown fences, no commentary.
- Paths must be absolute.

Tool signatures:
- search_file(path: str, pattern: str) -> matching file paths
- read_file(path: str) -> file contents
- edit_file(path: str, find: str, replace: str) -> confirmation
- write_file(path: str, content: str) -> confirmation
- shell_command(command: str) -> stdout/stderr"""


def build_prompt(user_request: str, tool_names: list[str]) -> tuple[str, str]:
    system = SYSTEM_PROMPT.format(tool_names=", ".join(tool_names))
    return system, user_request
