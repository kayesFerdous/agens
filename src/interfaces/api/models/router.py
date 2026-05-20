from __future__ import annotations

from datetime import timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.repositories.api_key import (
    APIKeyRepository,
    get_model_cooldown_info,
    is_model_available,
)
from interfaces.api.models.schemas import ModelInfo, ModelsResponse, ProviderModels
from llm.catalog import ModelEntry, get_catalog

router = APIRouter()

PROVIDER_NAMES = {
    "gemini": "Gemini",
    "openai": "OpenAI",
    "groq": "Groq",
    "cerebras": "Cerebras",
    "siliconflow": "SiliconFlow",
    "deepseek": "DeepSeek",
}

PROVIDER_ORDER = ("gemini", "openai", "groq", "cerebras", "siliconflow", "deepseek")


def _speed_label(speed_tps: int | None) -> str:
    if speed_tps is None:
        return "Moderate"
    if speed_tps >= 1500:
        return "Very fast"
    if speed_tps >= 400:
        return "Fast"
    return "Moderate"


def _quota_label(entry: ModelEntry) -> str:
    if not entry.free_tier:
        return "Paid API"
    free = entry.rate_limits.get("free", {})
    parts: list[str] = []
    if free.get("rpm"):
        parts.append(f"{free['rpm']:,} RPM")
    if free.get("rpd"):
        parts.append(f"{free['rpd']:,} RPD")
    if parts:
        return " · ".join(parts)
    return "Free tier available"


async def _model_status(
    repo: APIKeyRepository,
    keys: list,
    model_id: str,
) -> tuple[str, int | None]:
    if not keys:
        return "no_key", None

    cooldown_timestamps: list[int] = []
    for key in keys:
        await repo.cleanup_expired_cooldowns(key)
        if is_model_available(key, model_id):
            return "available", None

        cooldown = get_model_cooldown_info(key, model_id)
        if cooldown:
            available_at = cooldown["available_at"]
            if available_at.tzinfo is None:
                available_at = available_at.replace(tzinfo=timezone.utc)
            cooldown_timestamps.append(int(available_at.timestamp()))

    if cooldown_timestamps:
        return "cooldown", min(cooldown_timestamps)
    return "available", None


@router.get("/models", response_model=ModelsResponse)
async def list_models(db: AsyncSession = Depends(get_db)) -> ModelsResponse:
    repo = APIKeyRepository(db)
    providers: list[ProviderModels] = []

    for provider_id in PROVIDER_ORDER:
        entries = [
            entry
            for entry in get_catalog()
            if entry.provider == provider_id
        ]
        active_keys = await repo.get_active_by_provider(provider_id)
        models: list[ModelInfo] = []

        for entry in entries:
            status, cooldown_until_ts = await _model_status(repo, active_keys, entry.id)
            models.append(
                ModelInfo(
                    id=entry.id,
                    name=entry.name,
                    free_tier=entry.free_tier,
                    tool_calling=entry.tool_calling,
                    streaming=entry.streaming,
                    speed_label=_speed_label(entry.speed_tps),
                    quota_label=_quota_label(entry),
                    status=status,
                    cooldown_until_ts=cooldown_until_ts,
                )
            )

        providers.append(
            ProviderModels(
                id=provider_id,
                name=PROVIDER_NAMES[provider_id],
                has_active_key=bool(active_keys),
                models=models,
            )
        )

    return ModelsResponse(providers=providers)
