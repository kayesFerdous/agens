# tools/update_config.py
from __future__ import annotations

import json
from typing import Any

from core.tool_interface import Tool
from config.config_manager import ConfigManager


class UpdateConfigTool(Tool):
    """Thin tool wrapper around ConfigManager — parses JSON, delegates, returns result."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self._manager = config_manager

    @property
    def name(self) -> str:
        return "update_config"

    @property
    def description(self) -> str:
        return (
            "Update the assistant's config.json using a partial JSON object. "
            "Keys are deep-merged into the existing config (not overwritten wholesale). "
            "Only the top-level keys 'user', 'assistant', and 'preferences' are allowed. "
            "'user' and 'assistant' must always be objects with their respective fields, "
            "never plain strings."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "partial_config": {
                    "type": "string",
                    "description": (
                        "A JSON string containing the partial config to merge. "
                        "Example: '{\"user\": {\"name\": \"kayes\"}, "
                        "\"assistant\": {\"tone\": \"casual\"}}'"
                    ),
                },
            },
            "required": ["partial_config"],
        }

    def execute(self, **kwargs: Any) -> dict[str, Any]:
        raw: str = kwargs["partial_config"]

        # --- parse raw JSON string ---
        try:
            partial = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            return {"error": f"Invalid JSON input: {exc}"}

        if not isinstance(partial, dict):
            return {"error": "Input must be a JSON object, not a scalar or array."}

        # --- delegate to ConfigManager ---
        try:
            merged = self._manager.update_config(partial)
        except ValueError as exc:
            return {"error": str(exc)}
        except OSError as exc:
            return {"error": f"File write error: {exc}"}

        return {"status": "ok", "config": merged.model_dump()}
