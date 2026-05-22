"""add_device_table

Revision ID: 2cb3b626efa4
Revises: c3b2fc80fd62
Create Date: 2026-05-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString


revision: str = "2cb3b626efa4"
down_revision: Union[str, Sequence[str], None] = "c3b2fc80fd62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "device",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", AutoString(length=128), nullable=False),
        sa.Column("door_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", AutoString(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["door_id"], ["door.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_device_name"), "device", ["name"], unique=True)
    op.create_index(op.f("ix_device_door_id"), "device", ["door_id"])
    op.create_index(op.f("ix_device_token_hash"), "device", ["token_hash"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_device_token_hash"), table_name="device")
    op.drop_index(op.f("ix_device_door_id"), table_name="device")
    op.drop_index(op.f("ix_device_name"), table_name="device")
    op.drop_table("device")
