# tools/file_write.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool


class FileWriteTool(Tool):
    @property
    def name(self) -> str:
        return "write_file"

    def execute(self, **kwargs: Any) -> str:
        path: str = kwargs["path"]
        content: str = kwargs["content"]
        with open(path, "w") as f:
            f.write(content)
        return f"Wrote {len(content)} bytes to {path}"
