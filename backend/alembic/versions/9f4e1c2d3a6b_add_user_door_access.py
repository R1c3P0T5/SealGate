"""add_user_door_permission

Revision ID: 9f4e1c2d3a6b
Revises: 2cb3b626efa4
Create Date: 2026-05-28 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "9f4e1c2d3a6b"
down_revision: Union[str, Sequence[str], None] = "2cb3b626efa4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "userdoorpermission",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("door_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["door_id"], ["door.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id", "door_id", "action"),
    )
    op.create_index(
        op.f("ix_userdoorpermission_door_id"),
        "userdoorpermission",
        ["door_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_userdoorpermission_door_id"), table_name="userdoorpermission"
    )
    op.drop_table("userdoorpermission")
