# tools/file_search.py
from __future__ import annotations
import os
from typing import Any
from core.tool_interface import Tool


class FileSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_file"

    def execute(self, **kwargs: Any) -> str:
        path: str = kwargs["path"]
        pattern: str = kwargs["pattern"]
        matches: list[str] = []
        for root, _, files in os.walk(path):
            for f in files:
                if pattern in f:
                    matches.append(os.path.join(root, f))
        if not matches:
            return f"No files matching '{pattern}' found in {path}"
        return "\n".join(matches)
