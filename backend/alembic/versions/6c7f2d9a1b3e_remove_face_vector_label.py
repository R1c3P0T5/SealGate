"""remove_face_vector_label

Revision ID: 6c7f2d9a1b3e
Revises: 55ca21e0c5b6
Create Date: 2026-05-19 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString


revision: str = "6c7f2d9a1b3e"
down_revision: Union[str, Sequence[str], None] = "55ca21e0c5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("facevector") as batch_op:
        batch_op.drop_column("label")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("facevector") as batch_op:
        batch_op.add_column(sa.Column("label", AutoString(length=64), nullable=True))
