from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from services.settings_service import SettingsService
from .schemas import SettingsResponse, SettingsUpdateRequest

router = APIRouter()

@router.get("/", response_model=SettingsResponse)
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Retrieve the current application settings."""
    settings_service = SettingsService(db)
    settings = await settings_service.get_settings()
    return settings

@router.patch("/", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Update application settings.
    Uses PATCH semantics: only fields included in the request body will be updated.
    """
    settings_service = SettingsService(db)
    
    # Extract only fields that were explicitly set in the request
    update_data = request.model_dump(exclude_unset=True)
    
    if not update_data:
        # No fields provided for update, return the current settings
        return await settings_service.get_settings()
        
    try:
        updated_settings = await settings_service.update_settings(**update_data)
        return updated_settings
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
