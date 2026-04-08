from datetime import datetime

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionResponse(BaseModel):
    id: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
