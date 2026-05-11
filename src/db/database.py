from typing import AsyncGenerator
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import NullPool

from config.settings import settings

DATABASE_URL = settings.DATABASE_URL


def ensure_database_directory(database_url: str = DATABASE_URL) -> None:
    """Create the parent directory for file-backed SQLite databases."""
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return

    database = url.database
    if not database or database == ":memory:":
        return

    db_path = Path(database)
    db_path.parent.mkdir(parents=True, exist_ok=True)


ensure_database_directory()

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
)

async_session = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
