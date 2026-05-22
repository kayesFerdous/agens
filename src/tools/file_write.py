# tools/file_write.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool
from config.workspace import resolve_safe


class FileWriteTool(Tool):
    @property
    def name(self) -> str:
        return "file_write"

    @property
    def description(self) -> str:
        return "Write/overwrite file with content. Creates missing files."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to file.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write.",
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
