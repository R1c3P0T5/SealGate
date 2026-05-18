from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import hash_password
from src.roles.models import Role
from src.users.models import User


async def get_token(client: AsyncClient, username: str, password: str) -> str:
    response = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


async def create_user(
    database_session: AsyncSession,
    *,
    username: str | None = None,
    password: str = "UserPassword123",
    role_name: str = "user",
) -> User:
    username = username or f"user_{uuid4().hex[:12]}"
    role = (
        await database_session.exec(select(Role).where(Role.name == role_name))
    ).one()
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=hash_password(password),
        full_name="API User",
        role_id=role.id,
        is_active=True,
    )
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_user(client: AsyncClient, test_user: User) -> None:
    token = await get_token(client, test_user.username, "TestPassword123")

    response = await client.get(
        f"/api/users/{test_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == test_user.username


@pytest.mark.asyncio
async def test_get_user_not_found(client: AsyncClient, test_admin: User) -> None:
    token = await get_token(client, test_admin.username, "AdminPassword123")

    response = await client.get(
        f"/api/users/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "User not found"


@pytest.mark.asyncio
async def test_update_own_user(client: AsyncClient, test_user: User) -> None:
    token = await get_token(client, test_user.username, "TestPassword123")

    response = await client.put(
        f"/api/users/{test_user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Updated Test User", "email": "updated@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Test User"
    assert response.json()["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_update_other_user_forbidden(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
    seeded_roles: dict[str, Role],
) -> None:
    other_user = await create_user(database_session)
    token = await get_token(client, test_user.username, "TestPassword123")

    response = await client.put(
        f"/api/users/{other_user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Blocked Update"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


@pytest.mark.asyncio
async def test_admin_can_update_other_users(
    client: AsyncClient,
    test_admin: User,
    test_user: User,
) -> None:
    token = await get_token(client, test_admin.username, "AdminPassword123")

    response = await client.put(
        f"/api/users/{test_user.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Admin Updated"},
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Admin Updated"


@pytest.mark.asyncio
async def test_delete_own_user(client: AsyncClient, test_user: User) -> None:
    token = await get_token(client, test_user.username, "TestPassword123")

    response = await client.delete(
        f"/api/users/{test_user.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_list_users_admin_only(
    client: AsyncClient,
    test_admin: User,
    test_user: User,
) -> None:
    user_token = await get_token(client, test_user.username, "TestPassword123")
    admin_token = await get_token(client, test_admin.username, "AdminPassword123")

    forbidden_response = await client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    allowed_response = await client.get(
        "/api/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert forbidden_response.status_code == 403
    assert allowed_response.status_code == 200
    assert allowed_response.json()["total"] == 2


@pytest.mark.asyncio
async def test_list_users_pagination(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
    seeded_roles: dict[str, Role],
) -> None:
    await create_user(database_session, username="firstuser")
    await create_user(database_session, username="seconduser")
    token = await get_token(client, test_admin.username, "AdminPassword123")

    response = await client.get(
        "/api/users?skip=1&limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["skip"] == 1
    assert data["limit"] == 1
    assert len(data["users"]) == 1
