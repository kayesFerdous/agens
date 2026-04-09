# config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Support multiple API keys separated by commas: "key1,key2,key3"
    # Falls back to single GOOGLE_API_KEY for backwards compatibility
    GOOGLE_API_KEYS: str = ""
    GOOGLE_API_KEY: str = ""  # Legacy single key support

    DEFAULT_MODEL: str = "gemini-2.5-flash-lite"
    DATABASE_URL: str
    FRONTEND_LINK: str
    SESSION_SECRET_KEY: str
    # Defaults to the running user's home dir; override via WORKSPACE_ROOT in .env
    WORKSPACE_ROOT: str = str(Path.home())

    # Key rotation settings
    RATE_LIMIT_COOLDOWN: float = 60.0  # seconds
    QUOTA_EXHAUSTED_COOLDOWN: float = 86400.0  # seconds (24 hours - Google quota resets daily)

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    def get_api_keys(self) -> list[str]:
        """Get list of API keys, supporting both single and multiple key configs."""
        keys: list[str] = []

        # First, try GOOGLE_API_KEYS (comma-separated)
        if self.GOOGLE_API_KEYS:
            keys.extend(k.strip() for k in self.GOOGLE_API_KEYS.split(",") if k.strip())

        # Fall back to single GOOGLE_API_KEY if no multi-key config
        if not keys and self.GOOGLE_API_KEY:
            keys.append(self.GOOGLE_API_KEY.strip())

        if not keys:
            raise ValueError(
                "No API keys configured. Set GOOGLE_API_KEYS='key1,key2' or GOOGLE_API_KEY='key'"
            )

        return keys


settings = Settings()  # type: ignore
