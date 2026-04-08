# tools/file_edit.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool
from config.workspace import resolve_safe


class FileEditTool(Tool):
    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Find and replace text in a file. Replaces all occurrences of 'find' with 'replace'."

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "path": {
                    "type": "STRING",
                    "description": "Absolute path to the file to edit.",
                },
                "find": {
                    "type": "STRING",
                    "description": "The exact text to search for.",
                },
                "replace": {
                    "type": "STRING",
                    "description": "The text to replace each occurrence with.",
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
