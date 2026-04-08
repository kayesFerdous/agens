# tools/find_file.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from core.tool_interface import Tool
from config.workspace import WORKSPACE_ROOT, SKIPPED_DIRS, resolve_safe


class FindFileTool(Tool):
    @property
    def name(self) -> str:
        return "find_file"

    @property
    def description(self) -> str:
        return (
            "Find files whose name contains the given pattern under the "
            "workspace root or a given subdirectory. Returns a list of matching absolute paths."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "pattern": {
                    "type": "STRING",
                    "description": "Substring to match against file names.",
                },
                "directory": {
                    "type": "STRING",
                    "description": "Absolute path to scope the search. Defaults to workspace root.",
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> dict:
        pattern: str = kwargs["pattern"]
        search_root = resolve_safe(kwargs["directory"]) if "directory" in kwargs else WORKSPACE_ROOT
        matches: list[str] = []

        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for f in files:
                if pattern in f:
                    matches.append(str(Path(root) / f))

        return {"matches": matches}
