from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db.models import KeyStatus
from db.repositories.api_key import APIKeyRepository
from interfaces.web.api.api_keys.schemas import (
    APIKeyCreateRequest,
    APIKeyResponse,
    APIKeyStatusUpdateRequest,
)
from services.api_key_manager import APIKeyManager

router = APIRouter()


@router.post("", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: APIKeyCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    repo = APIKeyRepository(db)
    manager = APIKeyManager(repo, request.app.state.fernet)

    raw_key = body.api_key.strip()
    provider = body.provider.strip()

    if not raw_key:
        raise HTTPException(status_code=400, detail="api_key cannot be empty")
    if not provider:
        raise HTTPException(status_code=400, detail="provider cannot be empty")

    try:
        created = await manager.add_key(raw_key=raw_key, provider=provider, label=body.label)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return created


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    provider: str | None = Query(default=None),
    status_filter: KeyStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    repo = APIKeyRepository(db)
    keys = await repo.list_keys(
        provider=provider.strip() if provider else None,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return keys


@router.get("/{key_id}", response_model=APIKeyResponse)
async def get_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = APIKeyRepository(db)
    key = await repo.get_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    return key


@router.patch("/{key_id}/status", response_model=APIKeyResponse)
async def update_api_key_status(
    key_id: str,
    body: APIKeyStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    repo = APIKeyRepository(db)
    key = await repo.get_by_id(key_id)
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    if body.status == KeyStatus.ACTIVE:
        await repo.clear_cooldown(key_id)
    else:
        await repo.update_status(key_id, body.status)

    updated = await repo.get_by_id(key_id)
    if not updated:
        raise HTTPException(status_code=404, detail="API key not found")
    return updated


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
):
    repo = APIKeyRepository(db)
    deleted = await repo.delete_by_id(key_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
