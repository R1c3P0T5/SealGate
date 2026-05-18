import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


@pytest_asyncio.fixture
async def full_setup(database_session: AsyncSession) -> dict:
    admin_role = Role(name="admin")
    user_role = Role(name="user")
    database_session.add(admin_role)
    database_session.add(user_role)
    await database_session.flush()

    perms = [
        Permission(name=n)
        for n in ("door:open", "door:read", "face:create", "users:read")
    ]
    for p in perms:
        database_session.add(p)
    await database_session.flush()

    for p in perms:
        database_session.add(RolePermission(role_id=admin_role.id, permission_id=p.id))
    # user_role only gets door:open
    database_session.add(
        RolePermission(role_id=user_role.id, permission_id=perms[0].id)
    )

    admin = User(
        username="admin_x",
        password_hash="h",
        full_name="A",
        role_id=admin_role.id,
        is_active=True,
    )
    regular = User(
        username="user_x",
        password_hash="h",
        full_name="U",
        role_id=user_role.id,
        is_active=True,
    )
    database_session.add(admin)
    database_session.add(regular)
    await database_session.commit()
    return {
        "admin": admin,
        "user": regular,
        "perms": perms,
        "admin_role": admin_role,
        "user_role": user_role,
    }


@pytest.mark.asyncio
async def test_list_permissions_returns_all(
    client: AsyncClient, full_setup: dict
) -> None:
    token = create_access_token(full_setup["user"].id)
    response = await client.get(
        "/api/permissions", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert len(response.json()["permissions"]) == 4


@pytest.mark.asyncio
async def test_get_user_permissions_self(client: AsyncClient, full_setup: dict) -> None:
    user = full_setup["user"]
    token = create_access_token(user.id)
    response = await client.get(
        f"/api/users/{user.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "door:open" in data["effective"]
    assert "face:create" not in data["effective"]


@pytest.mark.asyncio
async def test_get_user_permissions_other_user_forbidden(
    client: AsyncClient, full_setup: dict
) -> None:
    token = create_access_token(full_setup["user"].id)
    admin_id = full_setup["admin"].id
    response = await client.get(
        f"/api/users/{admin_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_put_user_permissions_admin_can_set_override(
    client: AsyncClient, full_setup: dict
) -> None:
    admin = full_setup["admin"]
    user = full_setup["user"]
    token = create_access_token(admin.id)

    response = await client.put(
        f"/api/users/{user.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"overrides": [{"permission": "face:create", "granted": True}]},
    )
    assert response.status_code == 200

    check = await client.get(
        f"/api/users/{user.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "face:create" in check.json()["effective"]


@pytest.mark.asyncio
async def test_put_user_permissions_non_admin_forbidden(
    client: AsyncClient, full_setup: dict
) -> None:
    user = full_setup["user"]
    token = create_access_token(user.id)
    response = await client.put(
        f"/api/users/{user.id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
        json={"overrides": []},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_put_user_role_changes_role(
    client: AsyncClient, full_setup: dict
) -> None:
    admin = full_setup["admin"]
    user = full_setup["user"]
    admin_role_id = full_setup["admin_role"].id
    token = create_access_token(admin.id)

    response = await client.put(
        f"/api/users/{user.id}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role_id": str(admin_role_id)},
    )
    assert response.status_code == 200
    assert response.json()["role_name"] == "admin"
