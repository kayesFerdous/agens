# tools/find_directory.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Any
from core.tool_interface import Tool
from config.workspace import WORKSPACE_ROOT, SKIPPED_DIRS


class FindDirectoryTool(Tool):
    @property
    def name(self) -> str:
        return "find_directory"

    @property
    def description(self) -> str:
        return (
            f"find_directory(name: str) -> matching directory paths under workspace root "
            f"({WORKSPACE_ROOT}). Use this to locate a directory by its exact name."
        )

    def execute(self, **kwargs: Any) -> str:
        name: str = kwargs["name"]
        matches: list[Path] = []

        # os.walk is used here for traversal performance over large trees.
        for root, dirs, _ in os.walk(WORKSPACE_ROOT):
            # Prune skipped dirs in-place so os.walk won't descend into them.
            dirs[:] = [d for d in dirs if d not in SKIPPED_DIRS and not d.startswith(".")]
            for d in dirs:
                if d == name:
                    matches.append(Path(root) / d)

        if not matches:
            return f"No directory named '{name}' found under {WORKSPACE_ROOT}"
        return "\n".join(str(p) for p in matches)
