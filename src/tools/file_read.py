# tools/file_read.py
from __future__ import annotations

import os
from typing import Any

from core.tool_interface import Tool
from config.workspace import resolve_safe

# Hard cap: never return more than this many lines in a single call.
# Forces the LLM to read in chunks rather than dumping the whole file.
_MAX_LINES = 200


class FileReadTool(Tool):

    # ------------------------------------------------------------------
    # Tool interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read a file. Three modes:\n"
            "1. metadata_only=true — file stats only (line count, size). Use first on any unknown file.\n"
            "2. start_line + end_line — read only that range. Use after a search tells you where to look.\n"
            "3. query — search for a string, returns matching lines + context.\n"
            f"Max {_MAX_LINES} lines returned per call. Never call with no params on large files."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "path": {
                    "type": "STRING",
                    "description": "Absolute path to the file.",
                },
                "start_line": {
                    "type": "INTEGER",
                    "description": "1-based start line (inclusive). Requires end_line."
                },
                "end_line": {
                    "type": "INTEGER",
                    "description": "1-based end line (inclusive). Requires start_line."
                },
                "query": {
                    "type": "STRING",
                    "description": "Search string. Returns matching lines + context. Case-insensitive."
                },
                "context_lines": {
                    "type": "INTEGER",
                    "description": "Lines of context around each match. Default 3."
                },
                "metadata_only": {
                    "type": "BOOLEAN",
                    "description": "If true, return only file stats. No content."
                },
            },
            "required": ["path"],
        }

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def execute(self, **kwargs: Any) -> dict:
        path = resolve_safe(kwargs["path"])

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # --- Mode 1: metadata only ---
        if kwargs.get("metadata_only"):
            return self._metadata(path)

        # --- Validate param combos ---
        has_range = "start_line" in kwargs or "end_line" in kwargs
        has_query = "query" in kwargs

        if has_range and has_query:
            raise ValueError(
                "Provide either a line range OR a query, not both."
            )
        if ("start_line" in kwargs) != ("end_line" in kwargs):
            raise ValueError(
                "start_line and end_line must be provided together."
            )

        # Read all lines once (we always need them for range/search)
        lines = self._read_lines(path)
        total_lines = len(lines)

        # --- Mode 2: line range ---
        if has_range:
            return self._read_range(
                path=path,
                lines=lines,
                start=kwargs["start_line"],
                end=kwargs["end_line"],
                total_lines=total_lines,
            )

        # --- Mode 3: search ---
        if has_query:
            return self._search(
                path=path,
                lines=lines,
                query=kwargs["query"],
                context_lines=int(kwargs.get("context_lines", 3)),
                total_lines=total_lines,
            )

        # --- No params: safe default (metadata + first chunk only) ---
        # Never silently dump the whole file.
        meta = self._metadata(path)
        if total_lines <= _MAX_LINES:
            # Small file — safe to return everything
            return {
                **meta,
                "mode": "full",
                "content": "".join(lines),
                "lines_returned": total_lines,
            }

        # Large file — return metadata + first chunk as preview
        preview = "".join(lines[:_MAX_LINES])
        return {
            **meta,
            "mode": "preview",
            "warning": (
                f"File has {total_lines} lines. Returning first {_MAX_LINES} "
                f"as preview. Use start_line/end_line or query to read "
                "specific sections."
            ),
            "content": preview,
            "lines_returned": _MAX_LINES,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_lines(self, path) -> list[str]:
        """Read all lines, auto-detecting encoding."""
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    return f.readlines()
            except UnicodeDecodeError:
                continue
        raise ValueError(
            f"Could not decode {path} as text. "
            "File may be binary."
        )

    def _metadata(self, path) -> dict:
        """Return file stats without reading content."""
        stat = os.stat(path)
        # Count lines efficiently without loading into memory
        try:
            with open(path, "rb") as f:
                line_count = sum(1 for _ in f)
            encoding = "utf-8"  # default assumption
        except Exception:
            line_count = None
            encoding = "unknown"

        return {
            "path": str(path),
            "mode": "metadata",
            "size_bytes": stat.st_size,
            "line_count": line_count,
            "encoding": encoding,
            "tip": (
                f"File has {line_count} lines. "
                "Use query param to search, or start_line/end_line to read a range."
            ),
        }

    def _read_range(
        self,
        path,
        lines: list[str],
        start: int,
        end: int,
        total_lines: int,
    ) -> dict:
        """Return lines[start..end] (1-based, inclusive)."""
        # Validate
        if start < 1:
            raise ValueError(f"start_line must be >= 1, got {start}")
        if end < start:
            raise ValueError(
                f"end_line ({end}) must be >= start_line ({start})"
            )
        if start > total_lines:
            raise ValueError(
                f"start_line {start} exceeds file length ({total_lines} lines)"
            )

        # Clamp end to file length
        end = min(end, total_lines)

        # Enforce hard cap
        requested = end - start + 1
        if requested > _MAX_LINES:
            end = start + _MAX_LINES - 1
            end = min(end, total_lines)
            truncated = True
        else:
            truncated = False

        # Slice (convert to 0-based)
        chunk = lines[start - 1 : end]
        content = "".join(chunk)

        result = {
            "path": str(path),
            "mode": "range",
            "start_line": start,
            "end_line": end,
            "lines_returned": len(chunk),
            "total_lines": total_lines,
            "content": content,
        }

        if truncated:
            result["warning"] = (
                f"Requested range exceeded {_MAX_LINES}-line cap. "
                f"Returned lines {start}–{end}. "
                "Call again with a new start_line to continue."
            )

        return result

    def _search(
        self,
        path,
        lines: list[str],
        query: str,
        context_lines: int,
        total_lines: int,
    ) -> dict:
        """Return matching lines with surrounding context."""
        context_lines = max(0, min(context_lines, 10))  # cap context at 10
        query_lower = query.lower()

        # Find all matching line indices (0-based)
        match_indices = {
            i for i, line in enumerate(lines)
            if query_lower in line.lower()
        }

        if not match_indices:
            return {
                "path": str(path),
                "mode": "search",
                "query": query,
                "total_lines": total_lines,
                "match_count": 0,
                "matches": [],
                "tip": "No matches found. Try a shorter or different query.",
            }

        # Expand matches with context, then merge overlapping windows
        windows = _merge_windows(
            match_indices=match_indices,
            context=context_lines,
            total=total_lines,
        )

        # Build result blocks, respecting the hard line cap
        blocks = []
        lines_consumed = 0

        for (win_start, win_end) in windows:
            if lines_consumed >= _MAX_LINES:
                break
            remaining = _MAX_LINES - lines_consumed
            win_end = min(win_end, win_start + remaining - 1)

            block_lines = lines[win_start : win_end + 1]
            match_line_numbers = [
                i + 1  # convert to 1-based
                for i in match_indices
                if win_start <= i <= win_end
            ]

            blocks.append({
                "start_line": win_start + 1,   # 1-based
                "end_line": win_end + 1,         # 1-based
                "match_lines": match_line_numbers,
                "content": "".join(block_lines),
            })
            lines_consumed += len(block_lines)

        total_matches = len(match_indices)
        shown_matches = sum(len(b["match_lines"]) for b in blocks)

        result = {
            "path": str(path),
            "mode": "search",
            "query": query,
            "total_lines": total_lines,
            "match_count": total_matches,
            "blocks_returned": len(blocks),
            "matches": blocks,
        }

        if shown_matches < total_matches:
            result["warning"] = (
                f"Found {total_matches} matches but only returned "
                f"{shown_matches} within the {_MAX_LINES}-line cap. "
                "Refine your query to narrow results."
            )

        return result


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _merge_windows(
    match_indices: set[int],
    context: int,
    total: int,
) -> list[tuple[int, int]]:
    """
    Expand each match index by +/- context lines, then merge
    overlapping or adjacent windows into contiguous spans.
    Returns a sorted list of (start, end) tuples (0-based, inclusive).
    """
    if not match_indices:
        return []

    # Build raw windows
    raw = sorted(
        (max(0, i - context), min(total - 1, i + context))
        for i in match_indices
    )

    # Merge overlapping/adjacent spans
    merged: list[tuple[int, int]] = [raw[0]]
    for start, end in raw[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged
