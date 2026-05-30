"""merge handsign and normalize-username heads

Revision ID: 4a76231804c3
Revises: f3a9c2e1b847, d32413388abd
Create Date: 2026-05-30 00:00:00.000000

"""

from typing import Sequence, Union

revision: str = "4a76231804c3"
down_revision: Union[str, Sequence[str], None] = ("f3a9c2e1b847", "d32413388abd")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
