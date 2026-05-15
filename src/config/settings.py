# config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .bootstrap import managed_settings_files
from .runtime import get_runtime_root


def default_database_path() -> Path:
    return get_runtime_root() / "agens.db"


def default_database_url() -> str:
    return f"sqlite+aiosqlite:///{default_database_path()}"


class Settings(BaseSettings):
    PRODUCTION: bool = True
    DEFAULT_MODEL: str = "gemini-2.5-flash-lite"
    DATABASE_URL: str = Field(default_factory=default_database_url)
    # Dev mode: separate frontend server (e.g., localhost:5173).
    # Leave empty for production (frontend served from /static & root).
    FRONTEND_LINK: str = ""
    SESSION_SECRET_KEY: str
    # Defaults to the running user's home dir; override via WORKSPACE_ROOT in .env
    WORKSPACE_ROOT: str = str(Path.home())

    # Key rotation settings
    RATE_LIMIT_COOLDOWN: float = 60.0  # seconds
    QUOTA_EXHAUSTED_COOLDOWN: float = 86400.0  # seconds (24 hours - Google quota resets daily)
    FERNET_SECRET: str

    # ── Safety mode (blocks destructive commands by default) ────────────────────
    # true  = sudo commands require user confirmation (safe default)
    # false = sudo commands are still blocked on web/telegram; TUI prompts for password
    SAFETY_MODE_ENABLED: bool = True

    # Web interface
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000

    # Telegram webhook (optional — if unset, falls back to long-polling)
    WEBHOOK_HOST: str = ""
    WEBHOOK_PORT: int = 8443

    @field_validator("SESSION_SECRET_KEY")
    @classmethod
    def validate_session_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("SESSION_SECRET_KEY must be at least 32 characters long")
        return value

    @field_validator("FERNET_SECRET")
    @classmethod
    def validate_fernet_secret(cls, value: str) -> str:
        from cryptography.fernet import Fernet

        try:
            Fernet(value.encode("ascii"))
        except Exception as exc:  # noqa: BLE001 - pydantic should expose a validation error.
            raise ValueError("FERNET_SECRET must be a valid Fernet key") from exc
        return value

    model_config = SettingsConfigDict(
        env_file=managed_settings_files(),
        env_prefix="",
        extra="ignore",
    )

settings = Settings()  # type: ignore
