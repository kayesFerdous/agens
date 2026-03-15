# planner/prompt_builder.py
from __future__ import annotations
import platform
from config.workspace import WORKSPACE_ROOT

PLATFORM = platform.system()

SYSTEM_PROMPT = """You are a planning agent for a file and shell automation assistant.
Given a user request, produce a JSON array of steps. Each step is an object with:
  - "tool": one of {{tool_names}}
  - "arguments": a dict of keyword arguments for that tool
  - "output_key" (optional): a short semantic name to store this step's result
  - "depends_on" (optional): a dict mapping argument names to output_keys from earlier steps

Workspace root: {workspace_root}

Rules:
- Maximum 10 steps.
- Use ONLY the tools listed above — no other tool names.
- Output ONLY the JSON array, no markdown fences, no commentary.
- NEVER use a path outside the workspace root ({workspace_root}).
- NEVER search from "/" or any system directory.
- To find a DIRECTORY by name, use `find_directory` (pass `name`, not a path).
- To find a FILE by name or pattern, use `find_file` (pass `pattern`, not a path).
- Skip hidden dirs (starting with "."), `.cache`, `.git`, `node_modules`, `__pycache__`.
- All paths in arguments must be absolute and must start with {workspace_root}.

Context passing:
- NEVER hardcode a path that will only be known after a previous step runs.
- If a step produces a result needed later, add "output_key" with a short name (e.g. "project_dir", "target_file").
- If a step needs a value from a previous step, add "depends_on" mapping the argument name to the earlier step's output_key.
- When searching for a file inside a specific directory, pass the directory via depends_on to the "directory" argument to scope the search.
- Omit "output_key" and "depends_on" when not needed.

Example — find a file inside a project directory:
[
  {{"tool": "find_directory", "arguments": {{"name": "my-project"}}, "output_key": "project_dir"}},
  {{"tool": "find_file", "arguments": {{"pattern": ".env"}}, "depends_on": {{"directory": "project_dir"}}, "output_key": "env_file"}},
  {{"tool": "read_file", "arguments": {{}}, "depends_on": {{"path": "env_file"}}}}
]

Tool signatures:
{{tool_signatures}}"""


def build_prompt(
    user_request: str,
    tool_descriptions: list[dict[str, str]],
) -> tuple[str, str]:
    tool_names = ", ".join(t["name"] for t in tool_descriptions)
    tool_signatures = "\n".join(f"- {t['description']}" for t in tool_descriptions)
    system = SYSTEM_PROMPT.format(workspace_root=WORKSPACE_ROOT).replace(
        "{tool_names}", tool_names
    ).replace("{tool_signatures}", tool_signatures)
    return system, user_request
