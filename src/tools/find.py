"""
tools/find.py  —  unified file + directory search under the workspace.
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from core.tool_interface import Tool
from config.workspace import WORKSPACE_ROOT, SKIPPED_DIRS, resolve_safe

# ── tunables ──────────────────────────────────────────────────────────────────
MAX_RESULTS = 50
# ──────────────────────────────────────────────────────────────────────────────


class FindTool(Tool):

    # ── Tool interface ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "find"

    @property
    def description(self) -> str:
        return "Find files/directories by name under the workspace. Default: substring match on filenames."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": (
                        "Name pattern to match. Behaviour depends on match_mode: "
                        "'substring' (default) — pattern appears anywhere in the name; "
                        "'exact' — name must equal pattern exactly; "
                        "'glob' — shell-style wildcards, e.g. '*.py', 'test_*'."
                    ),
                },
                "type": {
                    "type": "string",
                    "enum": ["file", "directory", "both"],
                    "description": "What to search for. Default 'file'.",
                    "default": "file",
                },
                "match_mode": {
                    "type": "string",
                    "enum": ["substring", "exact", "glob"],
                    "description": "How to match pattern against names. Default 'substring'.",
                    "default": "substring",
                },
                "directory": {
                    "type": "string",
                    "description": (
                        "Absolute path to scope the search. "
                        "Defaults to workspace root."
                    ),
                },
                "extension": {
                    "type": "string",
                    "description": (
                        "Only return files with this extension, e.g. '.py'. "
                        "Applies only when type='file' or type='both'. "
                        "Include the leading dot."
                    ),
                },
                "include_hidden": {
                    "type": "boolean",
                    "description": "Include names starting with '.'. Default false.",
                    "default": False,
                },
                "max_results": {
                    "type": "integer",
                    "description": f"Maximum results to return. Default {MAX_RESULTS}.",
                    "default": MAX_RESULTS,
                },
            },
            "required": ["pattern"],
        }

    def execute(self, **kwargs: Any) -> dict:
        pattern: str        = kwargs["pattern"]
        kind: str           = kwargs.get("type", "file")
        match_mode: str     = kwargs.get("match_mode", "substring")
        extension: str | None = kwargs.get("extension")
        include_hidden: bool = kwargs.get("include_hidden", False)
        max_results: int    = int(kwargs.get("max_results", MAX_RESULTS))

        # ── resolve search root ───────────────────────────────────────────────
        try:
            search_root = (
                resolve_safe(kwargs["directory"])
                if "directory" in kwargs
                else WORKSPACE_ROOT
            )
        except ValueError as exc:
            return {"status": "error", "error": str(exc)}

        if not Path(search_root).exists():
            return {
                "status": "error",
                "error": f"Directory not found: {kwargs.get('directory')!r}",
            }

        # ── build matcher ─────────────────────────────────────────────────────
        matcher = _build_matcher(pattern, match_mode)

        # ── walk ──────────────────────────────────────────────────────────────
        matches: list[str] = []
        total = 0

        for root, dirs, files in os.walk(search_root):
            # prune skipped + optionally hidden dirs in-place
            dirs[:] = [
                d for d in dirs
                if d not in SKIPPED_DIRS
                and (include_hidden or not d.startswith("."))
            ]

            if kind in ("directory", "both"):
                for d in dirs:
                    if matcher(d):
                        total += 1
                        if len(matches) < max_results:
                            matches.append(str(Path(root) / d))

            if kind in ("file", "both"):
                for f in files:
                    if not include_hidden and f.startswith("."):
                        continue
                    if extension and not f.lower().endswith(extension.lower()):
                        continue
                    if matcher(f):
                        total += 1
                        if len(matches) < max_results:
                            matches.append(str(Path(root) / f))

        return {
            "status": "ok",
            "matches": matches,
            "total": total,
            "truncated": total > max_results,
        }


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_matcher(pattern: str, mode: str):
    """Return a callable(name: str) -> bool for the requested match mode."""
    if mode == "exact":
        return lambda name: name == pattern
    if mode == "glob":
        return lambda name: fnmatch.fnmatch(name, pattern)
    # default: substring
    return lambda name: pattern in name
