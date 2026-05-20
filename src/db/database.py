from typing import AsyncGenerator
from pathlib import Path

from sqlalchemy import event
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

url = make_url(DATABASE_URL)
is_sqlite = url.get_backend_name() == "sqlite"

connect_args = {}
if is_sqlite:
    connect_args["timeout"] = 30.0

engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args=connect_args,
)

if is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
