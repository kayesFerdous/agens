"""Application startup lifecycle helpers.

This module is the single entry point for process-level runtime preparation.
Commands that only inspect process/interface state call ``bootstrap_runtime``.
Commands that read or write persistent application data call
``bootstrap_database``.
"""

from __future__ import annotations

from config.runtime import initialize_runtime
from db.init import MigrationStatus, migrate_database


def bootstrap_runtime() -> None:
    """Prepare user-writable runtime directories and bundled defaults."""
    initialize_runtime()


async def bootstrap_database() -> MigrationStatus:
    """Prepare runtime files and migrate the local database when required."""
    bootstrap_runtime()
    return await migrate_database()

