# config/workspace.py
from __future__ import annotations
from pathlib import Path
from config.settings import settings

# Directory names that are always skipped during filesystem walks.
SKIPPED_DIRS: frozenset[str] = frozenset({
    ".cache", ".local", ".git", "node_modules",
    "__pycache__", "proc", "sys", ".venv", "venv",
})

# Workspace root — resolved once at import time.
WORKSPACE_ROOT: Path = Path(settings.WORKSPACE_ROOT).resolve()


def resolve_safe(path: str | Path) -> Path:
    """Resolve *path* and assert it lives inside WORKSPACE_ROOT.

    Raises:
        PermissionError: if the resolved path escapes the workspace.
    """
    resolved = Path(path).resolve()
    try:
        resolved.relative_to(WORKSPACE_ROOT)
    except ValueError:
        raise PermissionError(
            f"Path '{resolved}' is outside the workspace root '{WORKSPACE_ROOT}'. "
            "Only paths under the workspace root are allowed."
        )
    return resolved
