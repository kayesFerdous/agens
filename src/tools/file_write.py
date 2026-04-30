# tools/file_write.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool
from config.workspace import resolve_safe


class FileWriteTool(Tool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file. Creates the file if missing, overwrites if it exists."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to the file to write.",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file.",
                },
            },
            "required": ["path", "content"],
        }

    def execute(self, **kwargs: Any) -> dict:
        path = resolve_safe(kwargs["path"])
        content: str = kwargs["content"]
        with open(path, "w") as f:
            f.write(content)
        return {"path": str(path), "bytes_written": len(content)}
