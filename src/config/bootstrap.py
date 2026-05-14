"""First-run settings bootstrap for installed Agens applications.

This module owns the small, private env file that stores generated internal
secrets. It intentionally runs before Pydantic settings validation so a fresh
``pip install`` or ``pipx install`` can start without a user-created ``.env``.
"""

from __future__ import annotations

import base64
import binascii
import os
import secrets
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet

from .runtime import get_managed_env_file

MANAGED_CONFIG_VERSION = "1"

_HEADER = """# Agens managed runtime configuration.
# This file is generated on first run and stores per-user internal secrets.
# Environment variables can override these values.
# Set AGENS_ENV_FILE=/path/to/file to opt into an additional dotenv file.
"""

_MANAGED_KEYS = {
    "AGENS_MANAGED_CONFIG_VERSION",
    "SESSION_SECRET_KEY",
    "FERNET_SECRET",
}


class SettingsBootstrapError(RuntimeError):
    """Raised when Agens cannot create or repair its managed settings file."""


def ensure_managed_settings() -> Path:
    """Create or repair the per-user managed env file used by Pydantic.

    The file lives in the OS-specific user config directory provided by
    ``platformdirs``. Only Agens-owned internal defaults are written here; user
    configuration remains overridable through process environment variables or
    an explicit dotenv file selected with ``AGENS_ENV_FILE``.
    """

    path = get_managed_env_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        values = _read_env_file(path)
        legacy_values = _read_env_file(Path.cwd() / ".env") if not path.exists() else {}
        changed = False

        if values.get("AGENS_MANAGED_CONFIG_VERSION") != MANAGED_CONFIG_VERSION:
            values["AGENS_MANAGED_CONFIG_VERSION"] = MANAGED_CONFIG_VERSION
            changed = True

        if not _valid_session_secret(values.get("SESSION_SECRET_KEY")):
            values["SESSION_SECRET_KEY"] = (
                legacy_values.get("SESSION_SECRET_KEY")
                if _valid_session_secret(legacy_values.get("SESSION_SECRET_KEY"))
                else secrets.token_urlsafe(48)
            )
            changed = True

        if not _valid_fernet_secret(values.get("FERNET_SECRET")):
            values["FERNET_SECRET"] = (
                legacy_values.get("FERNET_SECRET")
                if _valid_fernet_secret(legacy_values.get("FERNET_SECRET"))
                else Fernet.generate_key().decode("ascii")
            )
            changed = True

        if changed or not path.exists():
            _write_env_file(path, values)
        else:
            _lock_down_permissions(path)

        return path
    except OSError as exc:
        raise SettingsBootstrapError(
            f"Unable to initialize Agens runtime settings at {path}: {exc}"
        ) from exc


def managed_settings_files() -> tuple[Path, ...]:
    """Return Pydantic dotenv files from lowest to highest precedence.

    Agens deliberately does not read ``.env`` from the current working
    directory by default. Installed command-line tools are often launched from
    unrelated project directories, and inheriting their dotenv files can
    silently corrupt application settings. Operators who need a dotenv file can
    opt in with ``AGENS_ENV_FILE=/path/to/file``.
    """

    files: list[Path] = [ensure_managed_settings()]
    explicit_env_file = os.environ.get("AGENS_ENV_FILE")
    if explicit_env_file:
        files.append(Path(explicit_env_file).expanduser())
    return tuple(files)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or path.stat().st_size == 0:
        return {}

    values: dict[str, str] = {}
    try:
        lines = path.read_text("utf-8").splitlines()
    except UnicodeDecodeError:
        return {}

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in _MANAGED_KEYS:
            values[key] = _unquote_env_value(value.strip())
    return values


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    content = _HEADER
    content += f"AGENS_MANAGED_CONFIG_VERSION={_quote_env_value(MANAGED_CONFIG_VERSION)}\n"
    content += f"SESSION_SECRET_KEY={_quote_env_value(values['SESSION_SECRET_KEY'])}\n"
    content += f"FERNET_SECRET={_quote_env_value(values['FERNET_SECRET'])}\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
        _lock_down_permissions(tmp_path)
        os.replace(tmp_path, path)
        _lock_down_permissions(path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _lock_down_permissions(path: Path) -> None:
    if os.name == "nt":
        return
    path.chmod(0o600)


def _valid_session_secret(value: str | None) -> bool:
    return isinstance(value, str) and len(value) >= 32


def _valid_fernet_secret(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        decoded = base64.urlsafe_b64decode(value)
    except (binascii.Error, ValueError):
        return False
    return len(decoded) == 32


def _quote_env_value(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value
