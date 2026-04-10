from datetime import datetime

from pydantic import BaseModel, Field

from db.models import KeyStatus


class APIKeyCreateRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=8)
    label: str | None = Field(default=None, max_length=200)


class APIKeyStatusUpdateRequest(BaseModel):
    status: KeyStatus


class APIKeyResponse(BaseModel):
    id: str
    label: str | None
    provider: str
    key_hint: str
    status: KeyStatus
    consecutive_failures: int
    cooldown_until: datetime | None
    last_used_at: datetime | None
    total_calls: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
