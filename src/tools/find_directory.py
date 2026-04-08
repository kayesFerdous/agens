# tools/find_directory.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from core.tool_interface import Tool
from config.workspace import WORKSPACE_ROOT, SKIPPED_DIRS, resolve_safe


class FindDirectoryTool(Tool):
    @property
    def name(self) -> str:
        return "find_directory"

    @property
    def description(self) -> str:
        return (
            "Find directories by name under the workspace root or a given "
            "subdirectory. Returns a list of matching absolute paths."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Exact directory name to search for.",
                },
                "directory": {
                    "type": "STRING",
                    "description": "Absolute path to scope the search. Defaults to workspace root.",
                },
            },
            "required": ["name"],
        }

    def execute(self, **kwargs: Any) -> dict:
        name: str = kwargs["name"]
        search_root = resolve_safe(kwargs["directory"]) if "directory" in kwargs else WORKSPACE_ROOT
        matches: list[str] = []

        for root, dirs, _ in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for d in dirs:
                if d == name:
                    matches.append(str(Path(root) / d))

        return {"matches": matches}
