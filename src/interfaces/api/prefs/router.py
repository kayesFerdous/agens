from __future__ import annotations

from fastapi import APIRouter

from interfaces.api.prefs.schemas import WebPrefsResponse, WebPrefsUpdate
from interfaces.web.prefs import get_selected_model, set_selected_model

router = APIRouter()


@router.get("/web", response_model=WebPrefsResponse)
async def get_web_prefs() -> WebPrefsResponse:
    return WebPrefsResponse(selected_model=get_selected_model())


@router.patch("/web", response_model=WebPrefsResponse)
async def update_web_prefs(body: WebPrefsUpdate) -> WebPrefsResponse:
    set_selected_model(body.selected_model)
    return WebPrefsResponse(selected_model=get_selected_model())
