from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db
from db import repository as session_repo
from interfaces.api.sessions.schemas import SessionCreateRequest, SessionDetailsResponse, SessionResponse

router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    body: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    session = await session_repo.insert_session(db, title=body.title)
    return session


@router.get("", response_model=list[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    sessions = await session_repo.fetch_all_sessions(db)
    return sessions


@router.get("/{session_id}", response_model=SessionDetailsResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await session_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    session = await session_repo.get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.delete(session)
    await db.commit()
