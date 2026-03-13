# tools/file_edit.py
from __future__ import annotations
from typing import Any
from core.tool_interface import Tool


class FileEditTool(Tool):
    @property
    def name(self) -> str:
        return "edit_file"

    def execute(self, **kwargs: Any) -> str:
        path: str = kwargs["path"]
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

        return f"Replaced {count} occurrence(s) of {find!r} with {replace!r} in {path}"
