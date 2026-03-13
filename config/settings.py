# config/settings.py
from __future__ import annotations
import os


def get_google_api_key() -> str:
    key = os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise EnvironmentError("GOOGLE_API_KEY environment variable is not set")
    return key


DEFAULT_MODEL = "gemini-2.5-flash-lite"
