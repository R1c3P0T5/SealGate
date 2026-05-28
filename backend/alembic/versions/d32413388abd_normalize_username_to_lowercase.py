"""normalize username to lowercase

Revision ID: d32413388abd
Revises: 9f4e1c2d3a6b
Create Date: 2026-05-29 00:12:06.742986

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d32413388abd"
down_revision: Union[str, Sequence[str], None] = "9f4e1c2d3a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            'SELECT LOWER(username), COUNT(*) FROM "user"'
            " GROUP BY LOWER(username) HAVING COUNT(*) > 1"
        )
    ).fetchall()
    if result:
        conflicts = ", ".join(row[0] for row in result)
        raise RuntimeError(
            f"Cannot normalize usernames: case-insensitive duplicates exist: {conflicts}. "
            "Resolve duplicate accounts before running this migration."
        )
    conn.execute(sa.text('UPDATE "user" SET username = LOWER(username)'))


def downgrade() -> None:
    """Downgrade schema."""
    pass
