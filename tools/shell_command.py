# tools/shell_command.py
from __future__ import annotations
import subprocess
from typing import Any
from core.tool_interface import Tool


class ShellCommandTool(Tool):
    @property
    def name(self) -> str:
        return "shell_command"

    @property
    def description(self) -> str:
        return "Run a shell command and return its stdout, stderr, and exit code."

    @property
    def parameters(self) -> dict:
        return {
            "type": "OBJECT",
            "properties": {
                "command": {
                    "type": "STRING",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        }

    def execute(self, **kwargs: Any) -> dict:
        command: str = kwargs["command"]
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
