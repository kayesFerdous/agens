import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from db.database import Base, engine


async def init_db():
    """Run Alembic migrations to create/update tables."""
    alembic_cfg = Config(Path(__file__).parent.parent / "alembic.ini")
    
    # Run in a separate thread since alembic uses sync code
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


async def create_tables_direct():
    """Create all tables directly (for development/testing only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_all_tables():
    """Drop all tables (use with caution!)"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
