"""Lightweight persistence for TUI user preferences.

Stored in the same ``data/`` directory the rest of the app uses.
File format is a single JSON object — safe to hand-edit.
"""
from __future__ import annotations

import json
from pathlib import Path

from config.runtime import get_runtime_root

# Resolves to  src/data/tui_prefs.json
_PREFS_FILE: Path = get_runtime_root() / "tui_prefs.json"

_DEFAULTS: dict = {
    "selected_model": None,
}


def _load() -> dict:
    try:
        return json.loads(_PREFS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def _save(prefs: dict) -> None:
    _PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))


# ── Public API ────────────────────────────────────────────────────────────────

def get_selected_model() -> str | None:
    """Return the persisted model ID, or None if no preference has been saved."""
    return _load().get("selected_model")


def set_selected_model(model_id: str | None) -> None:
    """Persist *model_id* so it survives restarts."""
    prefs = _load()
    prefs["selected_model"] = model_id
    _save(prefs)
