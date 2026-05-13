"""backfill session/message created_at as UTC

Revision ID: 2d1f4e7a6c9b
Revises: 8f6c1e2b9d3a
Create Date: 2026-05-13 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2d1f4e7a6c9b"
down_revision: Union[str, Sequence[str], None] = "8f6c1e2b9d3a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "UPDATE sessions "
            "SET created_at = (created_at AT TIME ZONE current_setting('TIMEZONE')) AT TIME ZONE 'UTC'"
        )
        op.execute(
            "UPDATE messages "
            "SET created_at = (created_at AT TIME ZONE current_setting('TIMEZONE')) AT TIME ZONE 'UTC'"
        )


def downgrade() -> None:
    """Downgrade schema."""
    pass
