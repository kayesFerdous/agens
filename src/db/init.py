import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from config.logging import get_logger
from db.database import Base, engine, ensure_database_directory

logger = get_logger(__name__)


async def init_db():
    """Run Alembic migrations to create/update tables."""
    ensure_database_directory()
    alembic_cfg = Config(Path(__file__).resolve().parent.parent.parent / "alembic.ini")
    
    # Check if alembic_version table exists
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        )
        has_alembic_version = result.fetchone() is not None
    
    if not has_alembic_version:
        # Check if sessions table exists (created by old init_db)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
            )
            has_sessions = result.fetchone() is not None
        
        if has_sessions:
            # Tables exist but Alembic doesn't know - stamp with current version
            logger.info("Existing tables found. Registering with Alembic...")
            await asyncio.to_thread(command.stamp, alembic_cfg, "head")
            logger.info("Database registered with Alembic.")
            return
    
    # Run migrations normally
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


async def create_tables_direct():
    """Create all tables directly (for development/testing only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables():
    """Drop all tables (use with caution!)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


if __name__ == "__main__":
    asyncio.run(init_db())
