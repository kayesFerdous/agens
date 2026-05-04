from pydantic import BaseModel
from typing import Optional


class SettingsUpdateRequest(BaseModel):
    # Make fields optional so we can support PATCH requests (partial updates)
    safety_mode: Optional[bool] = None


class SettingsResponse(BaseModel):
    safety_mode: bool

    model_config = {"from_attributes": True}
