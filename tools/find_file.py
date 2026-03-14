# tools/find_file.py
from __future__ import annotations
import os
from typing import Any
from core.tool_interface import Tool
from config.workspace import WORKSPACE_ROOT, SKIPPED_DIRS


class FindFileTool(Tool):
    @property
    def name(self) -> str:
        return "find_file"

    @property
    def description(self) -> str:
        return (
            f"find_file(pattern: str) -> file paths whose name contains *pattern*, "
            f"searched under workspace root ({WORKSPACE_ROOT}). "
            "Use this to locate a file by name or partial name."
        )

    def execute(self, **kwargs: Any) -> str:
        pattern: str = kwargs["pattern"]
        matches: list[str] = []

        for root, dirs, files in os.walk(WORKSPACE_ROOT):
            # Prune skipped dirs in-place so os.walk won't descend into them.
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for f in files:
                if pattern in f:
                    matches.append(os.path.join(root, f))

        if not matches:
            return f"No files matching '{pattern}' found under {WORKSPACE_ROOT}"
        return "\n".join(matches)
