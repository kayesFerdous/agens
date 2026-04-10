from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    title: str | None = None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailsResponse(SessionResponse):
    messages: list[MessageResponse] = []

