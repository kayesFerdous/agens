# config/settings.py
from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GOOGLE_API_KEY: str
    DEFAULT_MODEL: str = "gemini-2.5-flash-lite"
    # Defaults to the running user's home dir; override via WORKSPACE_ROOT in .env
    WORKSPACE_ROOT: str = str(Path.home())

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
