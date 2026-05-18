from uuid import uuid4

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from src.permissions.models import Permission, RolePermission, UserPermissionOverride
from src.roles.models import Role
from src.users.models import User


@pytest_asyncio.fixture
async def roles_and_perms(database_session: AsyncSession) -> dict:
    admin_role = Role(name="admin")
    user_role = Role(name="user")
    database_session.add(admin_role)
    database_session.add(user_role)
    await database_session.flush()

    perm_open = Permission(name="door:open")
    perm_read = Permission(name="door:read")
    perm_create = Permission(name="face:create")
    database_session.add(perm_open)
    database_session.add(perm_read)
    database_session.add(perm_create)
    await database_session.flush()

    database_session.add(
        RolePermission(role_id=user_role.id, permission_id=perm_open.id)
    )
    database_session.add(
        RolePermission(role_id=user_role.id, permission_id=perm_read.id)
    )
    for perm in (perm_open, perm_read, perm_create):
        database_session.add(
            RolePermission(role_id=admin_role.id, permission_id=perm.id)
        )

    await database_session.commit()
    return {
        "admin_role": admin_role,
        "user_role": user_role,
        "perm_open": perm_open,
        "perm_read": perm_read,
        "perm_create": perm_create,
    }


@pytest.mark.asyncio
async def test_user_permissions_returns_role_defaults(
    database_session: AsyncSession,
    roles_and_perms: dict,
) -> None:
    from src.core.permissions import user_permissions

    user = User(
        username=f"u_{uuid4().hex[:8]}",
        password_hash="h",
        full_name="Test",
        role_id=roles_and_perms["user_role"].id,
    )
    database_session.add(user)
    await database_session.commit()

    perms = await user_permissions(user, database_session)

    assert "door:open" in perms
    assert "door:read" in perms
    assert "face:create" not in perms


@pytest.mark.asyncio
async def test_override_granted_adds_permission_not_in_role(
    database_session: AsyncSession,
    roles_and_perms: dict,
) -> None:
    from src.core.permissions import user_permissions

    user = User(
        username=f"u_{uuid4().hex[:8]}",
        password_hash="h",
        full_name="Test",
        role_id=roles_and_perms["user_role"].id,
    )
    database_session.add(user)
    await database_session.flush()

    database_session.add(
        UserPermissionOverride(
            user_id=user.id,
            permission_id=roles_and_perms["perm_create"].id,
            granted=True,
        )
    )
    await database_session.commit()

    perms = await user_permissions(user, database_session)
    assert "face:create" in perms


@pytest.mark.asyncio
async def test_override_revoked_removes_permission_from_role(
    database_session: AsyncSession,
    roles_and_perms: dict,
) -> None:
    from src.core.permissions import user_permissions

    user = User(
        username=f"u_{uuid4().hex[:8]}",
        password_hash="h",
        full_name="Test",
        role_id=roles_and_perms["user_role"].id,
    )
    database_session.add(user)
    await database_session.flush()

    database_session.add(
        UserPermissionOverride(
            user_id=user.id,
            permission_id=roles_and_perms["perm_open"].id,
            granted=False,
        )
    )
    await database_session.commit()

    perms = await user_permissions(user, database_session)
    assert "door:open" not in perms
    assert "door:read" in perms
