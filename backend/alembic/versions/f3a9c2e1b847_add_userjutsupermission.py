"""add_userjutsupermission

Revision ID: f3a9c2e1b847
Revises: 1410fb0b412f
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f3a9c2e1b847"
down_revision: Union[str, Sequence[str], None] = "1410fb0b412f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "userjutsupermission",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("jutsu_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["jutsu_id"], ["jutsu.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id", "jutsu_id", "action"),
    )
    op.create_index(
        op.f("ix_userjutsupermission_jutsu_id"),
        "userjutsupermission",
        ["jutsu_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_userjutsupermission_jutsu_id"), table_name="userjutsupermission"
    )
    op.drop_table("userjutsupermission")
