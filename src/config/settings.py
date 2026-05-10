# config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DEFAULT_MODEL: str = "gemini-2.5-flash-lite"
    DATABASE_URL: str
    FRONTEND_LINK: str
    SESSION_SECRET_KEY: str
    # Defaults to the running user's home dir; override via WORKSPACE_ROOT in .env
    WORKSPACE_ROOT: str = str(Path.home())

    # Key rotation settings
    RATE_LIMIT_COOLDOWN: float = 60.0  # seconds
    QUOTA_EXHAUSTED_COOLDOWN: float = 86400.0  # seconds (24 hours - Google quota resets daily)
    FERNET_SECRET: str

    # ── Sudo authorization settings ───────────────────────────────────────────
    # true  = sudo commands are permanently blocked (safe default)
    # false = sudo allowed after confirmation + app secret verification
    SAFETY_MODE_ENABLED: bool = True
    # App-level secret users supply via /api/chat/authorize-sudo — NOT the OS password
    AGENT_SUDO_SECRET: str = ""
    # OS sudo password for the agent user — piped to stdin, never logged or in args
    SYSTEM_SUDO_PASSWORD: SecretStr = SecretStr("")  # type: ignore[assignment]

    # Web interface
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000

    # Telegram webhook (optional — if unset, falls back to long-polling)
    WEBHOOK_HOST: str = ""
    WEBHOOK_PORT: int = 8443

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

settings = Settings()  # type: ignore
