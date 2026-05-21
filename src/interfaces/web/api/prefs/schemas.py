from __future__ import annotations

from pydantic import BaseModel


class WebPrefsResponse(BaseModel):
    selected_model: str | None = None


class WebPrefsUpdate(BaseModel):
    selected_model: str | None = None
