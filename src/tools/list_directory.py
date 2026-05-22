"""
tools/list_directory.py  —  structured directory listing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.tool_interface import Tool

# ── tunables ──────────────────────────────────────────────────────────────────
DEFAULT_MAX_DEPTH = 2
MAX_ITEMS = 200
SKIPPED_DIRS = {
    ".git", ".hg", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", "dist", "build", ".mypy_cache", ".pytest_cache",
}
# ──────────────────────────────────────────────────────────────────────────────


class ListDirectoryTool(Tool):

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    # ── Tool interface ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "list_directory"

    @property
    def description(self) -> str:
        return "List directory files and subdirectories."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute path to directory.",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Recurse into subdirectories (default false).",
                    "default": False,
                },
                "max_depth": {
                    "type": "integer",
                    "description": f"Max depth when recursive=true (default {DEFAULT_MAX_DEPTH}).",
                    "default": DEFAULT_MAX_DEPTH,
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include hidden items starting with '.' (default false).",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    def execute(self, **kwargs: Any) -> dict:
        path: str            = kwargs["path"]
        recursive: bool      = kwargs.get("recursive", False)
        max_depth: int       = kwargs.get("max_depth", DEFAULT_MAX_DEPTH)
        include_hidden: bool = kwargs.get("include_hidden", False)

        try:
            dirpath = self._resolve_safe(path)
        except ValueError as exc:
            return {"error": str(exc), "status": "error"}

        if not dirpath.exists():
            return {"error": f"Path not found: {path!r}", "status": "error"}
        if not dirpath.is_dir():
            return {"error": f"Not a directory: {path!r}", "status": "error"}

        all_files: list[dict] = []
        all_dirs: list[dict]  = []
        truncated = False

        def _recurse(current: Path, depth: int) -> None:
            nonlocal truncated
            if len(all_files) + len(all_dirs) >= MAX_ITEMS:
                truncated = True
                return

            files, dirs = self._list_one(current, include_hidden)
            all_files.extend(files)
            all_dirs.extend(dirs)

            if recursive and depth < max_depth:
                for d in dirs:
                    _recurse(Path(d["path"]), depth + 1)

        _recurse(dirpath, depth=1)

        return {
            "status": "ok",
            "path": str(dirpath),
            "files": all_files,
            "dirs": all_dirs,
            "total_files": len(all_files),
            "total_dirs": len(all_dirs),
            "truncated": truncated,
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _resolve_safe(self, raw: str) -> Path:
        p = Path(raw).resolve()
        if self._workspace_root not in [p, *p.parents]:
            raise ValueError(
                f"Path {raw!r} is outside workspace root {self._workspace_root!r}"
            )
        return p

    def _list_one(
        self,
        dirpath: Path,
        include_hidden: bool,
    ) -> tuple[list[dict], list[dict]]:
        files: list[dict] = []
        dirs: list[dict]  = []

        try:
            entries = sorted(
                dirpath.iterdir(),
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except PermissionError:
            return files, dirs

        for entry in entries:
            if not include_hidden and entry.name.startswith("."):
                continue
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIPPED_DIRS:
                    dirs.append({"name": entry.name, "path": str(entry)})
            elif entry.is_file():
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = -1
                files.append({
                    "name": entry.name,
                    "size_bytes": size,
                    "extension": entry.suffix.lower() or None,
                })

        return files, dirs
