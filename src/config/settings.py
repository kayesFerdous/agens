# config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    CONFIG_PATH: Path = BASE_DIR / "data" / "config.json"

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

    # Web interface
    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000

    # Telegram webhook (optional — if unset, falls back to long-polling)
    WEBHOOK_HOST: str = ""
    WEBHOOK_PORT: int = 8443

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

settings = Settings()  # type: ignore
