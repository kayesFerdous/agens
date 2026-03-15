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
            "find_file(pattern: str, directory: str = WORKSPACE_ROOT) -> file paths "
            "whose name contains *pattern*. Pass 'directory' to scope the search to a "
            "subdirectory (e.g. from a previous find_directory result)."
        )

    def execute(self, **kwargs: Any) -> str:
        pattern: str = kwargs["pattern"]
        search_root = resolve_safe(kwargs["directory"]) if "directory" in kwargs else WORKSPACE_ROOT
        matches: list[Path] = []

        for root, dirs, files in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for f in files:
                if pattern in f:
                    matches.append(Path(root) / f)

        if not matches:
            return f"No files matching '{pattern}' found under {search_root}"
        return "\n".join(str(p) for p in matches)

