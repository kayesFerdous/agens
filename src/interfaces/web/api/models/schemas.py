from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


ModelStatus = Literal["available", "cooldown", "no_key"]


class ModelInfo(BaseModel):
    id: str
    name: str
    free_tier: bool
    tool_calling: bool
    streaming: bool
    speed_label: str
    quota_label: str
    status: ModelStatus
    cooldown_until_ts: int | None


class ProviderModels(BaseModel):
    id: str
    name: str
    has_active_key: bool
    models: list[ModelInfo]


class ModelsResponse(BaseModel):
    providers: list[ProviderModels]
