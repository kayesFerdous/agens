# tools/file_read.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool
from config.workspace import resolve_safe


class FileReadTool(Tool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read and return the contents of a file at the given absolute path."

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "path": {
                    "type": "STRING",
                    "description": "Absolute path to the file to read.",
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> dict:
        path = resolve_safe(kwargs["path"])
        with open(path, "r") as f:
            content = f.read()
        return {"path": str(path), "content": content}
