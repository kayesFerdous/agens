from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, field_serializer


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


class _UtcSerializedModel(BaseModel):
    model_config = {"from_attributes": True}

    @field_serializer("created_at", check_fields=False)
    def _serialize_created_at(self, value: datetime) -> str:
        return _to_utc_iso(value)


class SessionCreateRequest(BaseModel):
    title: str | None = None


class MessageResponse(_UtcSerializedModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime



class SessionResponse(_UtcSerializedModel):
    id: str
    title: str | None
    created_at: datetime



class SessionDetailsResponse(SessionResponse):
    messages: list[MessageResponse] = []

