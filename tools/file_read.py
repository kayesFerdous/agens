# tools/file_read.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool


class FileReadTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    def execute(self, **kwargs: Any) -> str:
        path: str = kwargs["path"]
        with open(path, "r") as f:
            return f.read()
