import pytest
from httpx import AsyncClient

from src.auth.utils import create_access_token
from src.roles.models import Role
from src.users.models import User


@pytest.fixture
def setup_roles(seeded_roles: dict[str, Role]) -> dict:
    # seeded_roles already gives door:read to user_role.
    return {
        "admin_role": seeded_roles["admin"],
        "user_role": seeded_roles["user"],
    }


@pytest.mark.asyncio
async def test_list_roles_returns_all_roles(
    client: AsyncClient, test_user: User, setup_roles: dict
) -> None:
    token = create_access_token(test_user.id)
    response = await client.get(
        "/api/roles", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    names = {r["name"] for r in data["roles"]}
    assert "admin" in names
    assert "user" in names


@pytest.mark.asyncio
async def test_get_role_by_id(
    client: AsyncClient, test_user: User, setup_roles: dict
) -> None:
    token = create_access_token(test_user.id)
    role_id = setup_roles["user_role"].id
    response = await client.get(
        f"/api/roles/{role_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "user"


@pytest.mark.asyncio
async def test_get_role_not_found(
    client: AsyncClient, test_user: User, setup_roles: dict
) -> None:
    from uuid import uuid4

    token = create_access_token(test_user.id)
    response = await client.get(
        f"/api/roles/{uuid4()}", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_role_permissions_returns_seeded_perms(
    client: AsyncClient, test_user: User, setup_roles: dict
) -> None:
    token = create_access_token(test_user.id)
    role_id = setup_roles["user_role"].id
    response = await client.get(
        f"/api/roles/{role_id}/permissions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert any(p["name"] == "door:read" for p in data["permissions"])


@pytest.mark.asyncio
async def test_list_role_users_requires_admin(
    client: AsyncClient, test_user: User, setup_roles: dict
) -> None:
    token = create_access_token(test_user.id)
    role_id = setup_roles["user_role"].id
    response = await client.get(
        f"/api/roles/{role_id}/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_role_users_returns_users_for_admin(
    client: AsyncClient, test_admin: User, setup_roles: dict
) -> None:
    token = create_access_token(test_admin.id)
    role_id = setup_roles["user_role"].id
    response = await client.get(
        f"/api/roles/{role_id}/users", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
