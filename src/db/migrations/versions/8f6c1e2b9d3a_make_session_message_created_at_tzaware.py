"""make session/message created_at timezone aware

Revision ID: 8f6c1e2b9d3a
Revises: 2349849567d7
Create Date: 2026-05-13 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f6c1e2b9d3a"
down_revision: Union[str, Sequence[str], None] = "2349849567d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("sessions") as batch:
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )

    with op.batch_alter_table("messages") as batch:
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("messages") as batch:
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )

    with op.batch_alter_table("sessions") as batch:
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
            existing_server_default=sa.text("(CURRENT_TIMESTAMP)"),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
        )
