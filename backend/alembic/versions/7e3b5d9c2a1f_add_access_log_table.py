"""add_access_log_table

Revision ID: 7e3b5d9c2a1f
Revises: 3f9c1d2e4b5a
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString


revision: str = "7e3b5d9c2a1f"
down_revision: Union[str, Sequence[str], None] = "3f9c1d2e4b5a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "accesslog",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("door_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("username", AutoString(length=128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("door_opened", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["door_id"], ["door.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accesslog_door_id"), "accesslog", ["door_id"])
    op.create_index(op.f("ix_accesslog_user_id"), "accesslog", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_accesslog_user_id"), table_name="accesslog")
    op.drop_index(op.f("ix_accesslog_door_id"), table_name="accesslog")
    op.drop_table("accesslog")
