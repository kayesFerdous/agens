"""Lightweight persistence for Telegram user preferences."""
from __future__ import annotations

import json
from pathlib import Path

from config.runtime import get_runtime_root
from core.tool_groups import normalize_tool_groups

_PREFS_FILE: Path = get_runtime_root() / "telegram_prefs.json"

_DEFAULTS: dict = {
    "users": {},
}


def _load() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def _save(prefs: dict) -> None:
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))


def get_selected_model(user_id: int) -> str | None:
    prefs = _load()
    users = prefs.get("users", {})
    user_prefs = users.get(str(user_id), {})
    return user_prefs.get("selected_model")


def set_selected_model(user_id: int, model_id: str | None) -> None:
    prefs = _load()
    users = prefs.setdefault("users", {})
    user_prefs = users.setdefault(str(user_id), {})
    user_prefs["selected_model"] = model_id
    _save(prefs)


def get_tool_groups(user_id: int) -> dict[str, bool]:
    prefs = _load()
    users = prefs.get("users", {})
    user_prefs = users.get(str(user_id), {})
    return normalize_tool_groups(user_prefs.get("tool_groups"))


def set_tool_groups(user_id: int, tool_groups: dict[str, bool]) -> None:
    prefs = _load()
    users = prefs.setdefault("users", {})
    user_prefs = users.setdefault(str(user_id), {})
    user_prefs["tool_groups"] = normalize_tool_groups(tool_groups)
    _save(prefs)
