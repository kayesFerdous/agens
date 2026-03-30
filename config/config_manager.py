# config/config_manager.py
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError


# ── Schema ──────────────────────────────────────────────────────


class UserConfig(BaseModel):
    name: str = ""


class AssistantConfig(BaseModel):
    name: str = ""
    tone: str = "friendly"


class PreferencesConfig(BaseModel):
    model_config = {"extra": "allow"}


class AppConfig(BaseModel):
    user: UserConfig = UserConfig()
    assistant: AssistantConfig = AssistantConfig()
    preferences: PreferencesConfig = PreferencesConfig()

    def to_system_prompt(self) -> str:
        return (
            f"Username: {self.user.name}. "
            f"Assistant's name: {self.assistant.name} "
            f"and speaks in a {self.assistant.tone} tone."
        )


# ── Manager ─────────────────────────────────────────────────────

ALLOWED_KEYS = {"user", "assistant", "preferences"}


class ConfigManager:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load_config(self) -> AppConfig:
        """Read config.json → AppConfig. Creates default file if missing."""
        if not self._path.exists() or self._path.stat().st_size == 0:
            default = AppConfig()
            self.save_config(default)
            return default

        raw = json.loads(self._path.read_text("utf-8"))
        return self._validate(raw)

    def save_config(self, config: AppConfig) -> None:
        """Write an AppConfig to disk."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(config.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def update_config(self, partial: dict[str, Any]) -> AppConfig:
        """Deep-merge partial dict into current config, validate, save."""
        bad = set(partial) - ALLOWED_KEYS
        if bad:
            raise ValueError(f"Disallowed keys: {sorted(bad)}")

        current = self.load_config().model_dump()
        merged = self._deep_merge(current, partial)
        config = self._validate(merged)
        self.save_config(config)
        return config

    # ── helpers ──────────────────────────────────────────────────

    @staticmethod
    def _validate(data: dict[str, Any]) -> AppConfig:
        """Parse a dict into AppConfig or raise ValueError."""
        try:
            return AppConfig(**data)
        except ValidationError as exc:
            raise ValueError(f"Invalid config: {exc}") from exc

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge override into a copy of base."""
        result = deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigManager._deep_merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result
