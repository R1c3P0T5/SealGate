"""normalize rbac uuid storage

Revision ID: c3b2fc80fd62
Revises: b7701dd24432
Create Date: 2026-05-22 22:00:12.737147

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3b2fc80fd62"
down_revision: Union[str, Sequence[str], None] = "b7701dd24432"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def normalize_sqlite_rbac_uuid_storage(connection: sa.Connection) -> None:
    if connection.dialect.name != "sqlite":
        return

    connection.execute(sa.text("PRAGMA foreign_keys=OFF"))
    connection.execute(
        sa.text(
            'UPDATE "user" '
            "SET role_id = replace(role_id, '-', '') "
            "WHERE role_id LIKE '%-%'"
        )
    )
    connection.execute(
        sa.text(
            "UPDATE rolepermission "
            "SET role_id = replace(role_id, '-', '') "
            "WHERE role_id LIKE '%-%'"
        )
    )
    connection.execute(
        sa.text("UPDATE role SET id = replace(id, '-', '') WHERE id LIKE '%-%'")
    )
    connection.execute(sa.text("PRAGMA foreign_keys=ON"))


def upgrade() -> None:
    """Upgrade schema."""
    normalize_sqlite_rbac_uuid_storage(op.get_bind())


def downgrade() -> None:
    """Downgrade schema."""
    pass
