"""
src/config/runtime.py

Centralized runtime configuration and path management.

Responsibilities:
- Define all runtime/config paths (single source of truth)
- Initialize runtime directories on first launch
- Copy default bundled assets without overwriting user edits
- Provide knowledge file listing for tool use
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from platformdirs import user_config_path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application identity
# ---------------------------------------------------------------------------

APP_NAME = "vela"  # change to your actual application name
APP_AUTHOR = None     # set to your org/author string if desired on Windows

# ---------------------------------------------------------------------------
# Source (bundled) asset paths  — relative to this file's package root
# ---------------------------------------------------------------------------

_THIS_FILE = Path(__file__).resolve()
# Assumes layout:  src/config/runtime.py  →  repo root is three levels up
_REPO_ROOT = _THIS_FILE.parents[2]
BUNDLED_ASSETS_DIR: Path = _REPO_ROOT / "assets"
BUNDLED_KNOWLEDGE_DIR: Path = BUNDLED_ASSETS_DIR / "knowledge"
BUNDLED_PROMPTS_DIR: Path = BUNDLED_ASSETS_DIR / "prompts"

# ---------------------------------------------------------------------------
# Runtime (user-writable) paths
# ---------------------------------------------------------------------------

def get_runtime_root() -> Path:
    """Return the root of the user-specific runtime config directory."""
    return user_config_path(APP_NAME, APP_AUTHOR)


def get_config_file() -> Path:
    return get_runtime_root() / "config.json"


def get_knowledge_dir() -> Path:
    return get_runtime_root() / "knowledge"


def get_prompts_dir() -> Path:
    return get_runtime_root() / "prompts"


def get_sessions_dir() -> Path:
    return get_runtime_root() / "sessions"


def get_logs_dir() -> Path:
    return get_runtime_root() / "logs"


# ---------------------------------------------------------------------------
# Directory initialisation
# ---------------------------------------------------------------------------

_RUNTIME_SUBDIRS = [
    get_knowledge_dir,
    get_prompts_dir,
    get_sessions_dir,
    get_logs_dir,
]


def ensure_runtime_dirs() -> None:
    """Create all runtime directories if they do not already exist."""
    root = get_runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    log.debug("Runtime root: %s", root)

    for dir_fn in _RUNTIME_SUBDIRS:
        path = dir_fn()
        path.mkdir(parents=True, exist_ok=True)
        log.debug("Ensured directory: %s", path)


# ---------------------------------------------------------------------------
# Asset copying — never overwrites existing user files
# ---------------------------------------------------------------------------

def copy_default_assets(force: bool = False) -> None:
    """
    Copy bundled default assets into the runtime config directory.

    Parameters
    ----------
    force:
        If True, overwrite existing runtime files with bundled defaults.
        Use with caution — this will discard user edits.
        Default is False (safe, preserves user edits).
    """
    _copy_tree(BUNDLED_KNOWLEDGE_DIR, get_knowledge_dir(), force=force)
    _copy_tree(BUNDLED_PROMPTS_DIR, get_prompts_dir(), force=force)


def _copy_tree(src: Path, dst: Path, *, force: bool = False) -> None:
    """
    Recursively copy *src* directory into *dst*.

    Skips individual files that already exist in *dst* unless *force* is True.
    Missing parent directories are created automatically.
    """
    if not src.exists():
        log.debug("Bundled source not found, skipping: %s", src)
        return

    for src_file in src.rglob("*"):
        if not src_file.is_file():
            continue

        relative = src_file.relative_to(src)
        dst_file = dst / relative

        if dst_file.exists() and not force:
            log.debug("Skipping existing user file: %s", dst_file)
            continue

        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)
        log.info("Copied asset: %s → %s", src_file, dst_file)


# ---------------------------------------------------------------------------
# First-run initialisation (call once at application startup)
# ---------------------------------------------------------------------------

def initialize_runtime(force_copy: bool = False) -> None:
    """
    Full initialisation sequence for the runtime environment.

    Call this once at application startup (e.g. in main.py or app.__init__).

    Steps
    -----
    1. Create all runtime directories.
    2. Copy bundled default assets (skips files already present unless
       *force_copy* is True).

    Parameters
    ----------
    force_copy:
        Passed through to copy_default_assets(). Leave False in production.
    """
    log.info("Initialising runtime at: %s", get_runtime_root())
    ensure_runtime_dirs()
    copy_default_assets(force=force_copy)
    log.info("Runtime initialisation complete.")


# ---------------------------------------------------------------------------
# Knowledge file discovery  (used by search_knowledge / list_knowledge tools)
# ---------------------------------------------------------------------------

def list_knowledge_files(
    subdirectory: str | None = None,
    extension: str = ".md",
) -> list[Path]:
    """
    Return a sorted list of knowledge files from the runtime knowledge dir.

    Parameters
    ----------
    subdirectory:
        Optional sub-folder name (e.g. ``"telegram"``).
        If None, all knowledge files are returned recursively.
    extension:
        File extension filter (default ``".md"``).
        Pass ``"*"`` or ``""`` to return all file types.

    Returns
    -------
    list[Path]
        Absolute paths to matching knowledge files, sorted for stable output.
    """
    base = get_knowledge_dir()
    if subdirectory:
        base = base / subdirectory

    if not base.exists():
        log.warning("Knowledge directory not found: %s", base)
        return []

    pattern = f"*{extension}" if extension and extension != "*" else "*"
    files = sorted(p for p in base.rglob(pattern) if p.is_file())
    log.debug("Found %d knowledge file(s) under %s", len(files), base)
    return files


def get_knowledge_index() -> dict[str, list[str]]:
    """
    Return a nested index of all knowledge files grouped by their
    immediate sub-folder name.

    Useful for injecting a compact file map into the system prompt or
    for powering a search_knowledge tool.

    Example return value::

        {
            "telegram": ["setup_channel.md", "add_bot.md", "permissions.md"],
            "discord":  ["overview.md"],
            "github":   ["actions.md", "webhooks.md"],
        }
    """
    knowledge_root = get_knowledge_dir()
    index: dict[str, list[str]] = {}

    for file in list_knowledge_files():
        try:
            relative = file.relative_to(knowledge_root)
        except ValueError:
            continue

        parts = relative.parts
        # Group by the first path component (sub-folder); use "." for root files
        group = parts[0] if len(parts) > 1 else "."
        index.setdefault(group, []).append(relative.as_posix())

    return index


def resolve_knowledge_path(relative_path: str) -> Path | None:
    """
    Resolve a relative knowledge path (as returned by list_knowledge_files
    or get_knowledge_index) to an absolute runtime path.

    Returns None if the resolved path does not exist or escapes the
    knowledge directory (path traversal guard).

    Parameters
    ----------
    relative_path:
        E.g. ``"telegram/setup_channel.md"``
    """
    knowledge_root = get_knowledge_dir()
    candidate = (knowledge_root / relative_path).resolve()

    # Security: ensure the resolved path stays inside the knowledge root
    try:
        candidate.relative_to(knowledge_root.resolve())
    except ValueError:
        log.warning("Path traversal attempt blocked: %s", relative_path)
        return None

    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# Convenience: compact system-prompt snippet
# ---------------------------------------------------------------------------

def build_knowledge_prompt_snippet() -> str:
    """
    Return a compact, model-friendly description of available knowledge files
    suitable for inclusion in a system prompt.

    The snippet is intentionally small — it tells the model *what exists*
    without injecting the actual file contents.
    """
    index = get_knowledge_index()
    if not index:
        return "No knowledge files are currently available."

    lines = ["Available knowledge files (use search_knowledge / read_file to access):"]
    for group, files in sorted(index.items()):
        label = group if group != "." else "(root)"
        lines.append(f"\n  [{label}]")
        for f in files:
            lines.append(f"    - {f}")

    return "\n".join(lines)
