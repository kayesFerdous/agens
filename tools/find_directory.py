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
            "find_directory(name: str, directory: str = WORKSPACE_ROOT) -> matching "
            "directory paths. Pass 'directory' to scope the search to a subdirectory."
        )

    def execute(self, **kwargs: Any) -> str:
        name: str = kwargs["name"]
        search_root = resolve_safe(kwargs["directory"]) if "directory" in kwargs else WORKSPACE_ROOT
        matches: list[Path] = []

        for root, dirs, _ in os.walk(search_root):
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for d in dirs:
                if d == name:
                    matches.append(Path(root) / d)

        if not matches:
            return f"No directory named '{name}' found under {search_root}"
        return "\n".join(str(p) for p in matches)
