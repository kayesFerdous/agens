from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from config.settings import settings

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    # aiosqlite is a file-based, single-writer DB — connection pooling gives no
    # throughput benefit and creates a hard-to-fix bug: when an ASGI streaming
    # task is cancelled (e.g. client disconnects), SQLAlchemy's pool tries to
    # rollback and return the connection, but the event loop is in a cancelled
    # state, causing cascading CancelledError / "no active connection" tracebacks.
    # NullPool sidesteps all of this: each session opens a fresh connection and
    # closes it directly — no pool, no _finalize_fairy, no reset on cancel.
    poolclass=NullPool,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
