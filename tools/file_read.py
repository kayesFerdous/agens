# tools/file_read.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool


class FileReadTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "read_file(path: str) -> file contents"

    def execute(self, **kwargs: Any) -> str:
        path: str = kwargs["path"]
        with open(path, "r") as f:
            return f.read()
