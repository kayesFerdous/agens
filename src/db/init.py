import asyncio
import json
import os
import tempfile
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from config.logging import get_logger
from config.runtime import get_runtime_root
from db.database import Base, DATABASE_URL, engine, ensure_database_directory

logger = get_logger(__name__)


@dataclass(frozen=True)
class MigrationStatus:
    """Result of a database bootstrap attempt."""

    revision: str
    migrated: bool
    reason: str


def _alembic_config() -> Config:
    """Build Alembic configuration from packaged migration resources."""
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("prepend_sys_path", ".")
    cfg.set_main_option("path_separator", "os")
    cfg.set_main_option("sqlalchemy.url", "driver://user:pass@localhost/dbname")
    return cfg


def _schema_state_file() -> Path:
    return get_runtime_root() / "db_state.json"


def _installed_app_version() -> str:
    try:
        return version("agens")
    except PackageNotFoundError:
        return "0+local"


def _migration_head(alembic_cfg: Config) -> str:
    return ScriptDirectory.from_config(alembic_cfg).get_current_head()


def _database_identity(database_url: str = DATABASE_URL) -> str:
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
        return str(Path(url.database).expanduser().resolve())
    return url.render_as_string(hide_password=True)


def _database_file_exists(database_url: str = DATABASE_URL) -> bool:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return True
    if not url.database or url.database == ":memory:":
        return True
    return Path(url.database).expanduser().exists()


def _read_schema_state() -> dict[str, Any]:
    path = _schema_state_file()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_schema_state(*, revision: str) -> None:
    path = _schema_state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_revision": revision,
        "database": _database_identity(),
        "app_version": _installed_app_version(),
    }

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2, ensure_ascii=True)
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def _schema_state_is_current(*, revision: str) -> bool:
    if not _database_file_exists():
        return False

    state = _read_schema_state()
    return (
        state.get("schema_revision") == revision
        and state.get("database") == _database_identity()
    )


async def _table_names() -> set[str]:
    async with engine.connect() as conn:
        table_names = await conn.run_sync(
            lambda sync_conn: inspect(sync_conn).get_table_names()
        )
        return set(table_names)


async def _table_columns(table_name: str) -> set[str]:
    async with engine.connect() as conn:
        return set(
            await conn.run_sync(
                lambda sync_conn: [
                    column["name"]
                    for column in inspect(sync_conn).get_columns(table_name)
                ]
            )
        )


async def _has_alembic_version_table() -> bool:
    return "alembic_version" in await _table_names()


async def _legacy_revision_for_unversioned_database(head_revision: str) -> str | None:
    """Infer the safest Alembic revision for databases created before Alembic.

    Older releases created tables directly with SQLAlchemy and therefore have
    no ``alembic_version`` row. We stamp the closest known revision, then let
    Alembic apply the remaining migrations normally.
    """

    tables = await _table_names()
    if not tables:
        return None

    if not {"sessions", "messages"}.issubset(tables):
        raise RuntimeError(
            "Existing database is missing required core tables and is not "
            "managed by Alembic."
        )

    if "api_keys" not in tables:
        return "001"

    api_key_columns = await _table_columns("api_keys")
    removed_api_key_columns = {"consecutive_failures", "cooldown_until", "total_calls"}
    if "model_cooldowns" not in api_key_columns:
        return "fb4736f26bf9"
    if api_key_columns & removed_api_key_columns:
        return "6aa5b8df0d23"
    if "settings" not in tables:
        return "740c09128175"
    if "schedule_events" not in tables:
        return "2d1f4e7a6c9b"

    schedule_columns = await _table_columns("schedule_events")
    if "session_id" in schedule_columns:
        return "c4e9a7b2d1f0"

    return head_revision


async def _stamp_legacy_database_if_needed(alembic_cfg: Config, head_revision: str) -> None:
    if await _has_alembic_version_table():
        return

    legacy_revision = await _legacy_revision_for_unversioned_database(head_revision)
    if legacy_revision is None:
        return

    logger.info(
        "Existing unversioned database found. Registering Alembic revision %s.",
        legacy_revision,
    )
    await asyncio.to_thread(command.stamp, alembic_cfg, legacy_revision)


async def migrate_database(force: bool = False) -> MigrationStatus:
    """Bring the local database schema to the packaged Alembic head.

    The fast path reads a small runtime marker and avoids touching Alembic or
    opening the database when the installed migration head is already applied.
    """

    ensure_database_directory()
    alembic_cfg = _alembic_config()
    head_revision = _migration_head(alembic_cfg)

    if not force and _schema_state_is_current(revision=head_revision):
        return MigrationStatus(revision=head_revision, migrated=False, reason="current")

    await _stamp_legacy_database_if_needed(alembic_cfg, head_revision)
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")
    _write_schema_state(revision=head_revision)
    return MigrationStatus(revision=head_revision, migrated=True, reason="upgraded")


async def init_db() -> MigrationStatus:
    """Backward-compatible alias for database bootstrap."""
    return await migrate_database()


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
