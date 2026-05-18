# llm/providers.py
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ProviderConfig:
    """Everything needed to talk to one LLM provider."""
    name: str
    base_url: str
    api_key: str
    default_model: str
    timeout: float = 60.0
    supports_streaming: bool = True
    # Some providers don't handle parallel tool calls reliably.
    parallel_tool_calls: bool = True
    # Some providers need tool_choice forced to avoid ignoring tools.
    force_tool_choice: bool = False


# Canonical provider definitions — the only place base URLs live.
# api_key is populated at runtime from your encrypted DB.
PROVIDER_DEFAULTS: dict[str, dict] = {
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
        "parallel_tool_calls": False,   # Gemini OpenAI compat is picky here
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5.5",
        "parallel_tool_calls": True,
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "parallel_tool_calls": True,
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "default_model": "llama-3.3-70b",
        "parallel_tool_calls": True,
    },
    "siliconflow": {
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
        "parallel_tool_calls": True,
    },
}


def build_provider_config(provider_name: str, api_key: str, model: str | None = None) -> ProviderConfig:
    """Build a ProviderConfig from the defaults registry + a live API key."""
    defaults = PROVIDER_DEFAULTS.get(provider_name)
    if defaults is None:
        raise ValueError(f"Unknown provider: {provider_name!r}. Valid: {list(PROVIDER_DEFAULTS)}")
    return ProviderConfig(
        name=provider_name,
        api_key=api_key,
        default_model=model or defaults["default_model"],
        **{k: v for k, v in defaults.items() if k != "default_model"},
    )
