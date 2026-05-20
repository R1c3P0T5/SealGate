"""merge_access_log_and_face_vector_heads

Revision ID: b7701dd24432
Revises: 6c7f2d9a1b3e, 7e3b5d9c2a1f
Create Date: 2026-05-20 16:23:50.604881

"""

from typing import Sequence, Union


revision: str = "b7701dd24432"
down_revision: Union[str, Sequence[str], None] = ("6c7f2d9a1b3e", "7e3b5d9c2a1f")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
