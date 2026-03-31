from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Message, Session


async def create_session(db: AsyncSession, title: str | None = None) -> Session:
    session = Session(title=title)
    db.add(session)
    await db.commit()
    return session


async def get_session(db: AsyncSession, session_id: str) -> Session | None:
    return await db.get(Session, session_id)


async def list_sessions(db: AsyncSession, limit: int = 20) -> list[Session]:
    result = await db.execute(
        select(Session).order_by(Session.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


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


async def get_messages(db: AsyncSession, session_id: str) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())
