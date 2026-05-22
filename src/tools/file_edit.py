# tools/file_edit.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool
from config.workspace import resolve_safe


class FileEditTool(Tool):
    @property
    def name(self) -> str:
        return "file_edit"

    @property
    def description(self) -> str:
        return "Find-and-replace text in a file. Replaces ALL occurrences."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to file.",
                },
                "find": {
                    "type": "string",
                    "description": "Exact text to find.",
                },
                "replace": {
                    "type": "string",
                    "description": "Replacement text.",
                },
            },
            "required": ["path", "find", "replace"],
        }

    def execute(self, **kwargs: Any) -> dict:
        path = resolve_safe(kwargs["path"])
        find: str = kwargs["find"]
        replace: str = kwargs["replace"]

        with open(path, "r") as f:
            content = f.read()

        if find not in content:
            raise ValueError(f"Pattern not found in {path}: {find!r}")

        count = content.count(find)
        new_content = content.replace(find, replace)

        with open(path, "w") as f:
            f.write(new_content)

        return {"path": str(path), "replacements": count, "find": find, "replace": replace}
