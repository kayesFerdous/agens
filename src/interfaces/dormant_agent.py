from __future__ import annotations

from cryptography.fernet import Fernet

from agent.agent import Agent
from agent.factory import _build_registry
from config.config_manager import ConfigManager
from config.settings import settings
from llm.client import LLMClient
from llm.providers import build_provider_config
from llm.router import FreeTierRouter


def build_dormant_agent() -> Agent:
    """Build an Agent without selecting an API key at startup.

    The first message send still goes through the normal LLM key selection path.
    This is only for interfaces that need to load while keys exist but none are
    currently usable.
    """
    fernet = Fernet(settings.FERNET_SECRET)
    config_manager = ConfigManager()
    registry = _build_registry(config_manager)
    router = FreeTierRouter(fernet)
    provider_name = getattr(settings, "DEFAULT_PROVIDER", "gemini")
    model = getattr(settings, "DEFAULT_MODEL", "") or None
    llm = LLMClient(build_provider_config(provider_name, api_key="sk-dormant-placeholder", model=model))
    llm.current_key_id = None  # type: ignore[attr-defined]
    return Agent(
        registry=registry,
        llm=llm,
        router=router,
        config_manager=config_manager,
        fernet=fernet,
    )
