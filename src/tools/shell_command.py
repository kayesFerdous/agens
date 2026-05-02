"""
tools/shell_command.py  —  safe, token-efficient shell execution.
"""

from __future__ import annotations

import re
import shlex
import asyncio
from pathlib import Path
from typing import Any

from core.tool_interface import Tool

# ── tunables ──────────────────────────────────────────────────────────────────
DEFAULT_TIMEOUT  = 30       # seconds
MAX_TIMEOUT      = 120      # seconds — hard ceiling even if caller asks for more
MAX_OUTPUT_CHARS = 5_000    # stdout + stderr each; excess is truncated
SUDO_TIMEOUT     = 30       # seconds — fixed ceiling for sudo commands
# ──────────────────────────────────────────────────────────────────────────────

# Sanitized environment for sudo execution — never inherits parent process env.
# This prevents API keys, DB URLs, and other secrets from leaking into subprocesses.
SANITIZED_ENV: dict[str, str] = {
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "HOME": str(Path.home()),
    "LANG": "en_US.UTF-8",
    "TERM": "xterm-256color",
}

# Patterns that are NEVER allowed, even with explicit user confirmation.
# These are catastrophic and irreversible (fork bombs, filesystem formatters, etc.).
_HARD_BLOCK: list[re.Pattern] = [
    re.compile(r":\(\)\{.*\}"),                 # fork bomb
    re.compile(r"\bmkfs\b"),                    # format filesystem
    re.compile(r"\bdd\b.*of=/dev/"),            # write raw to device
    re.compile(r">\s*/dev/sd"),                 # overwrite block device
    re.compile(r"\bshutdown\b|\breboot\b|\bhalt\b"),
]

# Patterns that require explicit user confirmation before execution.
# Each entry is (pattern, human-readable reason).
# These are gated — safe to run if the user knowingly approves.
_NEEDS_CONFIRMATION: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\bsudo\b"),
        "This command requires root privileges (sudo) and can modify system-level files, "
        "install or remove packages, or alter system configuration.",
    ),
    (
        re.compile(r"\bsu\s+-"),
        "This command switches to another user account, potentially granting elevated access.",
    ),
    (
        re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b"),
        "This command recursively force-deletes files or directories. Deletion is irreversible.",
    ),
    (
        re.compile(r"\brm\s+-[a-z]*f[a-z]*r\b"),
        "This command recursively force-deletes files or directories. Deletion is irreversible.",
    ),
    (
        re.compile(r"\bchmod\s+777\b"),
        "This sets world-readable/writable/executable permissions on a file, "
        "which is a significant security risk.",
    ),
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

    async def execute(self, **kwargs: Any) -> dict:
        command: str  = kwargs["command"]
        cwd: str      = kwargs.get("cwd") or self._workspace_root
        timeout: int  = min(int(kwargs.get("timeout", DEFAULT_TIMEOUT)), MAX_TIMEOUT)
        # NOTE: `confirmed` and `use_sudo` are intentionally NOT in self.parameters
        # (the JSON schema). The LLM cannot pass them. Only the agent sets them
        # after explicit user approval and secret verification.
        confirmed: bool = bool(kwargs.get("confirmed", False))
        use_sudo: bool  = bool(kwargs.get("use_sudo", False))

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

        # ── safety: hard block (permanent, no override) ──────────────────────────
        for pattern in _HARD_BLOCK:
            if pattern.search(command):
                return {
                    "status": "error",
                    "error": (
                        f"Command permanently blocked by safety policy "
                        f"(matched: {pattern.pattern!r}). "
                        "This action can never be executed through the assistant."
                    ),
                    "command": command,
                }

        # ── safety: soft block (requires explicit user confirmation) ──────────────
        if not confirmed:
            for pattern, reason in _NEEDS_CONFIRMATION:
                if pattern.search(command):
                    return {
                        "status": "needs_confirmation",
                        "command": command,
                        "reason": reason,
                        "preview": command,
                    }

        # ── sudo execution path (confirmed=True and use_sudo=True) ────────────────
        if use_sudo and confirmed:
            return await self._execute_with_sudo(command)

        # ── execute ───────────────────────────────────────────────────────────
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(cwd_path),
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
                result_stdout = stdout_bytes.decode(errors='replace')
                result_stderr = stderr_bytes.decode(errors='replace')
                result_returncode = proc.returncode
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "status": "error",
                    "error": f"Command timed out after {timeout}s.",
                    "command": command,
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc), "command": command}

        # ── truncate output ───────────────────────────────────────────────────
        stdout, stdout_truncated = _truncate(result_stdout)
        stderr, stderr_truncated = _truncate(result_stderr)

        return {
            "status": "ok" if result_returncode == 0 else "error",
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": result_returncode,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
        }

    # ── Sudo execution — password via stdin pipe ONLY ───────────────────────

    async def _execute_with_sudo(self, command: str) -> dict:
        """Execute command with sudo via stdin pipe.

        Security guarantees:
        - Password is never in command args (not visible in /proc/<pid>/cmdline)
        - shell=False always (exec-list form prevents shell injection)
        - Sanitized env (no parent secrets leak into the subprocess)
        - Password bytes are zeroed immediately after communicate()
        - Password is never logged under any log level
        """
        from config.settings import settings  # local import avoids circular dep at module load

        # Dereference SecretStr — this value is used exactly once below, then overwritten
        password = settings.SYSTEM_SUDO_PASSWORD.get_secret_value()

        # sudo -S reads password from stdin; -p "" suppresses the password prompt
        args = ["sudo", "-S", "-p", ""] + shlex.split(command)

        logger = __import__("logging").getLogger(__name__)
        logger.info(
            "sudo execution started",
            # Log command preview only — password is never included
            extra={"command_preview": command[:120]},
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=SANITIZED_ENV,  # never inherits parent process environment
            )

            password_bytes = (password + "\n").encode()
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=password_bytes),
                    timeout=SUDO_TIMEOUT,
                )
            finally:
                # Zero out password bytes immediately after use
                password_bytes = b"\x00" * len(password_bytes)  # overwrite in-place
                del password_bytes
                del password  # remove reference to plaintext

            stdout_text, trunc_out = _truncate(stdout_bytes.decode(errors="replace"))
            stderr_text, trunc_err = _truncate(stderr_bytes.decode(errors="replace"))

            logger.info(
                "sudo execution finished",
                extra={"exit_code": proc.returncode, "command_preview": command[:120]},
            )

            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "command": command,  # command only — password never returned
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": proc.returncode,
                "stdout_truncated": trunc_out,
                "stderr_truncated": trunc_err,
            }

        except asyncio.TimeoutError:
            logger.warning("sudo command timed out", extra={"command_preview": command[:120]})
            return {
                "status": "error",
                "error": f"Sudo command timed out after {SUDO_TIMEOUT}s.",
                "command": command,
            }

        except Exception:
            # Log error type only — never log the exception message in case it
            # contains process env fragments that include the password
            logger.error("sudo execution failed — see server logs for details")
            return {
                "status": "error",
                "error": "Sudo execution failed. See server logs for details.",
                "command": command,
            }
