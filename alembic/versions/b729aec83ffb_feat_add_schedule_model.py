"""feat: add schedule model

Revision ID: b729aec83ffb
Revises: c4e9a7b2d1f0
Create Date: 2026-05-13 11:35:22.789305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b729aec83ffb'
down_revision: Union[str, Sequence[str], None] = 'c4e9a7b2d1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return inspector.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Upgrade schema."""
    table_name = "schedule_events"
    index_name = op.f("ix_schedule_events_session_id")

    if _has_table(table_name) and _has_column(table_name, "session_id"):
        if _has_index(table_name, index_name):
            op.drop_index(index_name, table_name=table_name)
        op.drop_column(table_name, "session_id")


def downgrade() -> None:
    """Downgrade schema."""
    table_name = "schedule_events"
    index_name = op.f("ix_schedule_events_session_id")

    if _has_table(table_name) and not _has_column(table_name, "session_id"):
        op.add_column(table_name, sa.Column("session_id", sa.VARCHAR(), nullable=True))

    if _has_table(table_name) and _has_column(table_name, "session_id") and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, ["session_id"], unique=False)
