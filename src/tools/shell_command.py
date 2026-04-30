"""
tools/shell_command.py  —  safe, token-efficient shell execution.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from core.tool_interface import Tool

# ── tunables ──────────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT  = 30       # seconds
MAX_TIMEOUT      = 120      # seconds — hard ceiling even if caller asks for more
MAX_OUTPUT_CHARS = 5_000    # stdout + stderr each; excess is truncated
# ──────────────────────────────────────────────────────────────────────────────

# Patterns that are almost never legitimate in an AI coding assistant context.
# Checked against the raw command string before execution.
_BLOCKLIST: list[re.Pattern] = [
    re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b"),   # rm -rf variants
    re.compile(r"\brm\s+-[a-z]*f[a-z]*r\b"),   # rm -fr variants
    re.compile(r":\(\)\{.*\}"),                 # fork bomb
    re.compile(r"\bsudo\b"),                    # privilege escalation
    re.compile(r"\bsu\s+-"),                    # switch user
    re.compile(r"\bchmod\s+777\b"),             # world-writable
    re.compile(r"\bmkfs\b"),                    # format filesystem
    re.compile(r"\bdd\b.*of=/dev/"),            # write raw to device
    re.compile(r">\s*/dev/sd"),                 # overwrite block device
    re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b"),
]


def _truncate(text: str) -> tuple[str, bool]:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS], True


class ShellCommandTool(Tool):

    def __init__(self, workspace_root: str) -> None:
        self._workspace_root = str(Path(workspace_root).resolve())

    # ── Tool interface ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "shell_command"

    @property
    def description(self) -> str:
        return "Run a shell command. Returns stdout, stderr, exit_code. Use only when no structured tool fits. Prefer list_directory over ls, grep over grep -r, read_file over cat."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "cwd": {
                    "type": "string",
                    "description": (
                        "Absolute working directory for the command. "
                        "Defaults to workspace root. Must be inside workspace root."
                    ),
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        f"Seconds before the command is killed. "
                        f"Default {DEFAULT_TIMEOUT}, max {MAX_TIMEOUT}."
                    ),
                    "default": DEFAULT_TIMEOUT,
                },
            },
            "required": ["command"],
        }

    def execute(self, **kwargs: Any) -> dict:
        command: str    = kwargs["command"]
        cwd: str        = kwargs.get("cwd") or self._workspace_root
        timeout: int    = min(int(kwargs.get("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)

        # ── safety: resolve + validate cwd ───────────────────────────────────
        try:
            cwd_path = Path(cwd).resolve()
            root_path = Path(self._workspace_root).resolve()
            if root_path not in [cwd_path, *cwd_path.parents]:
                return {
                    "status": "error",
                    "error": (
                        f"cwd {cwd!r} is outside workspace root "
                        f"{self._workspace_root!r}"
                    ),
                    "command": command,
                }
            if not cwd_path.is_dir():
                return {
                    "status": "error",
                    "error": f"cwd not a directory: {cwd!r}",
                    "command": command,
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc), "command": command}

        # ── safety: blocklist check ───────────────────────────────────────────
        for pattern in _BLOCKLIST:
            if pattern.search(command):
                return {
                    "status": "error",
                    "error": (
                        f"Command blocked by safety policy "
                        f"(matched pattern: {pattern.pattern!r}). "
                        "If this is intentional, run it manually."
                    ),
                    "command": command,
                }

        # ── execute ───────────────────────────────────────────────────────────
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd_path),
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "error",
                "error": f"Command timed out after {timeout}s.",
                "command": command,
            }
        except Exception as exc:
            return {"status": "error", "error": str(exc), "command": command}

        # ── truncate output ───────────────────────────────────────────────────
        stdout, stdout_truncated = _truncate(result.stdout)
        stderr, stderr_truncated = _truncate(result.stderr)

        return {
            "status": "ok" if result.returncode == 0 else "error",
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result.returncode,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }
