from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.models import APIKey, KeyStatus, Message, Session

# ─────────────────────────────────────────
# Session
# ─────────────────────────────────────────

async def insert_session(db: AsyncSession, title: str | None = None) -> Session:
    session = Session(title=title)
    db.add(session)
    await db.commit()
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.messages))
    )
    return result.scalars().one_or_none()


async def fetch_all_sessions(
    db: AsyncSession, limit: int = 20, offset: int = 0
) -> list[Session]:
    result = await db.execute(
        select(Session)
        .order_by(Session.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ─────────────────────────────────────────
# Message
# ─────────────────────────────────────────

async def add_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    tool_calls: list[dict] | None = None,
) -> Message:
    message = Message(
        session_id=session_id,
        role=role,
        content=content,
        tool_calls=tool_calls,
    )
    db.add(message)
    await db.commit()
    return message


async def get_messages(
    db: AsyncSession, session_id: str, max_history: int = 3
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(max_history * 2)
    )
    return list(reversed(result.scalars().all()))


