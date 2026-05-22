"""
tools/grep.py  —  recursive content search across workspace files.

Collapses the common  find_file → read_file × N  pattern into one call.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from core.tool_interface import Tool

# ── tunables ──────────────────────────────────────────────────────────────────
MAX_RESULTS  = 50
MAX_LINE_LEN = 300
SKIPPED_DIRS = {
    ".git", ".hg", "__pycache__", "node_modules", ".venv", "venv",
    ".tox", "dist", "build", ".mypy_cache", ".pytest_cache",
}
SKIPPED_EXTS = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".whl", ".lock",
}
# ──────────────────────────────────────────────────────────────────────────────


class GrepTool(Tool):

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = Path(workspace_root).resolve()

    # ── Tool interface ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "grep"

    @property
    def description(self) -> str:
        return "Search file contents recursively for a pattern. Faster than find + read loops."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search.",
                },
                "path": {
                    "type": "string",
                    "description": "Directory or file path to search under (default: workspace root).",
                },
                "file_glob": {
                    "type": "string",
                    "description": "Filter files matching glob pattern (e.g., '*.py').",
                },
                "regex": {
                    "type": "boolean",
                    "description": "Treat pattern as regex (default false).",
                    "default": False,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Case-sensitive match (default true).",
                    "default": True,
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Max matching lines (default {MAX_RESULTS}).",
                    "default": MAX_RESULTS,
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> dict:
        pattern: str         = kwargs["pattern"]
        path: str | None     = kwargs.get("path")
        file_glob: str | None = kwargs.get("file_glob")
        regex: bool          = kwargs.get("regex", False)
        case_sensitive: bool = kwargs.get("case_sensitive", True)
        max_results: int     = kwargs.get("max_results", MAX_RESULTS)

        # ── resolve search root ───────────────────────────────────────────────
        try:
            search_root = self._resolve_safe(path or str(self._workspace_root))
        except ValueError as exc:
            return {"error": str(exc), "status": "error"}

        if not search_root.exists():
            return {"error": f"Path not found: {path!r}", "status": "error"}

        # ── compile matcher ───────────────────────────────────────────────────
        try:
            matcher = self._build_matcher(pattern, regex, case_sensitive)
        except re.error as exc:
            return {"error": f"Invalid regex: {exc}", "status": "error"}

        # ── walk + search ─────────────────────────────────────────────────────
        results: list[dict] = []
        total = 0
        files_searched = 0

        for fpath in self._iter_files(search_root, file_glob):
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            files_searched += 1
            for lineno, line in enumerate(text.splitlines(), 1):
                if matcher(line):
                    total += 1
                    if len(results) < max_results:
                        content = line[:MAX_LINE_LEN]
                        if len(line) > MAX_LINE_LEN:
                            content += "…"
                        results.append({
                            "path": str(fpath),
                            "line_number": lineno,
                            "line_content": content.strip(),
                        })

        return {
            "status": "ok",
            "matches": results,
            "total": total,
            "truncated": total > max_results,
            "files_searched": files_searched,
        }

    # ── private helpers ───────────────────────────────────────────────────────

    def _resolve_safe(self, raw: str) -> Path:
        p = Path(raw).resolve()
        if self._workspace_root not in [p, *p.parents]:
            raise ValueError(
                f"Path {raw!r} is outside workspace root {self._workspace_root!r}"
            )
        return p

    def _build_matcher(self, pattern: str, regex: bool, case_sensitive: bool):
        if regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
            return lambda line: bool(compiled.search(line))
        needle = pattern if case_sensitive else pattern.lower()
        if case_sensitive:
            return lambda line: needle in line
        return lambda line: needle in line.lower()

    def _iter_files(self, root: Path, file_glob: str | None):
        if root.is_file():
            yield root
            return
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIPPED_DIRS]
            for fname in filenames:
                if Path(fname).suffix.lower() in SKIPPED_EXTS:
                    continue
                if file_glob and not Path(fname).match(file_glob):
                    continue
                yield Path(dirpath) / fname
