from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_db

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"]
)

@router.get("")
async def get_session(db: AsyncSession = Depends(get_db)):
    

@router.get("/{session_id}")
async def read_single_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    asd
