import datetime
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlmodel.sql.sqltypes import AutoString

revision: str = "55ca21e0c5b6"
down_revision: Union[str, Sequence[str], None] = "57b2ec0178b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADMIN_ROLE_ID = str(uuid.uuid4())
_USER_ROLE_ID = str(uuid.uuid4())

_ALL_PERMISSIONS = [
    ("face:create", "Create face vectors"),
    ("face:read", "Read face vectors"),
    ("face:update", "Update face vectors"),
    ("face:delete", "Delete face vectors"),
    ("user:create", "Create users"),
    ("user:read", "Read user profiles"),
    ("user:update", "Update user profiles"),
    ("user:delete", "Delete users"),
    ("door:open", "Trigger door open"),
    ("door:read", "Read door information"),
    ("log:read", "Read access logs"),
]

_USER_PERMISSIONS = {"door:open", "door:read", "log:read"}


def upgrade() -> None:
    op.create_table(
        "role",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", AutoString(length=64), nullable=False),
        sa.Column("description", AutoString(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_role_name"), "role", ["name"], unique=True)

    op.create_table(
        "permission",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", AutoString(length=64), nullable=False),
        sa.Column("description", AutoString(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_permission_name"), "permission", ["name"], unique=True)

    op.create_table(
        "rolepermission",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    op.create_table(
        "userpermissionoverride",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permission.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "permission_id"),
    )
    op.create_index(
        op.f("ix_userpermissionoverride_user_id"),
        "userpermissionoverride",
        ["user_id"],
        unique=False,
    )

    now = datetime.datetime.utcnow().isoformat()
    op.execute(
        f"INSERT INTO role (id, name, description, created_at) VALUES "
        f"('{_ADMIN_ROLE_ID}', 'admin', 'Full access administrator', '{now}'), "
        f"('{_USER_ROLE_ID}', 'user', 'Standard user', '{now}')"
    )

    perm_ids: dict[str, str] = {}
    for name, description in _ALL_PERMISSIONS:
        perm_id = str(uuid.uuid4())
        perm_ids[name] = perm_id
        op.execute(
            f"INSERT INTO permission (id, name, description) VALUES "
            f"('{perm_id}', '{name}', '{description}')"
        )

    for name, perm_id in perm_ids.items():
        op.execute(
            f"INSERT INTO rolepermission (role_id, permission_id) VALUES "
            f"('{_ADMIN_ROLE_ID}', '{perm_id}')"
        )
        if name in _USER_PERMISSIONS:
            op.execute(
                f"INSERT INTO rolepermission (role_id, permission_id) VALUES "
                f"('{_USER_ROLE_ID}', '{perm_id}')"
            )

    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("role_id", sa.Uuid(), nullable=True))

    op.execute(
        f"UPDATE \"user\" SET role_id = '{_ADMIN_ROLE_ID}' WHERE role = 'admin'"
    )
    op.execute(
        f"UPDATE \"user\" SET role_id = '{_USER_ROLE_ID}' WHERE role = 'user'"
    )

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("role_id", nullable=False)
        batch_op.create_foreign_key("fk_user_role_id", "role", ["role_id"], ["id"])
        batch_op.drop_column("role")


def downgrade() -> None:
    with op.batch_alter_table("user") as batch_op:
        batch_op.add_column(sa.Column("role", AutoString(), nullable=True))

    op.execute(
        'UPDATE "user" SET role = (SELECT name FROM role WHERE role.id = "user".role_id)'
    )

    with op.batch_alter_table("user") as batch_op:
        batch_op.alter_column("role", nullable=False)
        batch_op.drop_constraint("fk_user_role_id", type_="foreignkey")
        batch_op.drop_column("role_id")

    op.drop_index(
        op.f("ix_userpermissionoverride_user_id"),
        table_name="userpermissionoverride",
    )
    op.drop_table("userpermissionoverride")
    op.drop_table("rolepermission")
    op.drop_index(op.f("ix_permission_name"), table_name="permission")
    op.drop_table("permission")
    op.drop_index(op.f("ix_role_name"), table_name="role")
    op.drop_table("role")
