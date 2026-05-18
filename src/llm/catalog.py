# llm/catalog.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True, slots=True)
class ModelEntry:
    id: str
    provider: str          # "gemini", "groq", "cerebras", "siliconflow"
    name: str
    free_tier: bool
    tool_calling: bool
    streaming: bool
    parallel_tool_calls: bool
    context_window: int
    speed_tps: Optional[int]   # tokens/sec, used for ranking
    rate_limits: dict          # {"free": {"rpm": 10, "rpd": 250, ...}}

# ------------------------------------------------------------------
# Flatten your research here.  Only models that are free + tool-call + stream.
# ------------------------------------------------------------------
_CATALOG: tuple[ModelEntry, ...] = (
    ModelEntry(
        id="gemini-2.5-flash-lite",
        provider="gemini",
        name="Gemini 2.5 Flash-Lite",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=1_048_576, speed_tps=2_000,
        rate_limits={"free": {"rpm": 15, "rpd": 1_000, "tpm": 250_000}},
    ),
    ModelEntry(
        id="gemini-2.5-flash",
        provider="gemini",
        name="Gemini 2.5 Flash",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=1_048_576, speed_tps=1_400,
        rate_limits={"free": {"rpm": 10, "rpd": 250, "tpm": 250_000}},
    ),
    ModelEntry(
        id="gemini-2.5-pro",
        provider="gemini",
        name="Gemini 2.5 Pro",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=1_048_576, speed_tps=800,
        rate_limits={"free": {"rpm": 5, "rpd": 100, "tpm": 250_000}},
    ),
    ModelEntry(
        id="llama-3.1-8b-instant",
        provider="groq",
        name="Llama 3.1 8B Instant",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=131_072, speed_tps=560,
        rate_limits={"free": {"rpm": 30, "rpd": 14_400, "tpm": 6_000, "tpd": 500_000}},
    ),
    ModelEntry(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        provider="groq",
        name="Llama 4 Scout",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=131_072, speed_tps=750,
        rate_limits={"free": {"rpm": 30, "rpd": 1_000, "tpm": 30_000, "tpd": 500_000}},
    ),
    ModelEntry(
        id="qwen/qwen3-32b",
        provider="groq",
        name="Qwen3 32B",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=131_072, speed_tps=400,
        rate_limits={"free": {"rpm": 60, "rpd": 1_000, "tpm": 6_000, "tpd": 500_000}},
    ),
    ModelEntry(
        id="gpt-oss-120b",
        provider="groq",
        name="GPT-OSS 120B",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=False,
        context_window=131_072, speed_tps=500,
        rate_limits={"free": {"rpm": 30, "rpd": 1_000, "tpm": 8_000, "tpd": 200_000}},
    ),
    ModelEntry(
        id="gpt-oss-120b",
        provider="cerebras",
        name="GPT OSS 120B (Cerebras)",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=131_072, speed_tps=3_000,
        rate_limits={"free": {"rpm": 30, "rpd": 14_400, "tpm": 60_000, "tpd": 1_000_000}},
    ),
    ModelEntry(
        id="Qwen/Qwen3-8B",
        provider="siliconflow",
        name="Qwen3-8B",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=131_072, speed_tps=None,
        rate_limits={"free": {"rpm": 1_000, "tpm": 50_000}},
    ),
    ModelEntry(
        id="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
        provider="siliconflow",
        name="DeepSeek-R1-Qwen3-8B",
        free_tier=True, tool_calling=True, streaming=True, parallel_tool_calls=True,
        context_window=33_000, speed_tps=None,
        rate_limits={"free": {"rpm": 1_000, "tpm": 50_000}},
    ),
)

# Fast lookup maps
_BY_ID: dict[str, ModelEntry] = {m.id: m for m in _CATALOG}

# Fallback chain: fastest / highest-quota first, then downward.
_FALLBACK_CHAIN: list[str] = [
    "gemini-2.5-flash-lite",
    "llama-3.1-8b-instant",
    "gemini-2.5-flash",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "qwen/qwen3-32b",
    "gemini-2.5-pro",
    "gpt-oss-120b",   # groq first; cerebras is same id, router de-dupes by provider
    "Qwen/Qwen3-8B",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
]

def get_model(model_id: str) -> ModelEntry | None:
    return _BY_ID.get(model_id)

def get_fallback_chain() -> list[ModelEntry]:
    """Return ordered, deduplicated entries that are free-tier capable."""
    seen: set[str] = set()
    out: list[ModelEntry] = []
    for mid in _FALLBACK_CHAIN:
        m = _BY_ID.get(mid)
        if m and m.free_tier and m.id not in seen:
            seen.add(m.id)
            out.append(m)
    return out

def cooldown_for(entry: ModelEntry, reason: str = "rate_limit") -> int:
    """Return seconds to cool down based on catalog rate limits."""
    free = entry.rate_limits.get("free", {})
    if reason == "exhausted" or free.get("rpd") or free.get("tpd"):
        # Daily/token limit: back off for an hour (or until midnight if you track it).
        return 3_600
    rpm = free.get("rpm")
    if rpm:
        # Wait one full bucket window + 1s jitter.
        return max(60 // rpm, 5)
    return 60
