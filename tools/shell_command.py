# tools/shell_command.py
from __future__ import annotations
import subprocess
from typing import Any
from core.tool_interface import Tool


class ShellCommandTool(Tool):
    @property
    def name(self) -> str:
        return "shell_command"

    def execute(self, **kwargs: Any) -> str:
        command: str = kwargs["command"]
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30,
        )
        output = result.stdout
        if result.returncode != 0:
            output += f"\nSTDERR:\n{result.stderr}" if result.stderr else ""
            raise RuntimeError(f"Command failed (exit {result.returncode}):\n{output}")
        return output or "(no output)"
