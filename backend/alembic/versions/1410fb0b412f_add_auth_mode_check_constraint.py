"""add_auth_mode_check_constraint

Revision ID: 1410fb0b412f
Revises: aeff7182bd97
Create Date: 2026-05-29 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "1410fb0b412f"
down_revision: Union[str, Sequence[str], None] = "aeff7182bd97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("door") as batch_op:
        batch_op.create_check_constraint(
            "door_auth_mode_check",
            "auth_mode IN ('face', 'handsign', 'both')",
        )


def downgrade() -> None:
    with op.batch_alter_table("door") as batch_op:
        batch_op.drop_constraint("door_auth_mode_check", type_="check")
