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
{tool_signatures}"""


def build_prompt(
    user_request: str,
    tool_descriptions: list[dict[str, str]],
) -> tuple[str, str]:
    tool_names = ", ".join(t["name"] for t in tool_descriptions)
    tool_signatures = "\n".join(f"- {t['description']}" for t in tool_descriptions)
    system = SYSTEM_PROMPT.format(tool_names=tool_names, tool_signatures=tool_signatures)
    return system, user_request
