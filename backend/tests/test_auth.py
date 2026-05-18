import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.roles.models import Role
from src.users.models import User


@pytest.mark.asyncio
async def test_register_success(
    client: AsyncClient, seeded_roles: dict[str, Role]
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "newuser",
            "password": "NewPassword123",
            "full_name": "New User",
            "email": "newuser@example.com",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role_name"] == "user"
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_register_duplicate_username(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": test_user.username,
            "password": "AnotherPassword123",
            "full_name": "Duplicate User",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Username already in use"


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/register",
        json={
            "username": "weakuser",
            "password": "short",
            "full_name": "Weak User",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "TestPassword123"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["user"]["username"] == test_user.username


@pytest.mark.asyncio
async def test_login_invalid_password(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "WrongPassword123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "missing", "password": "MissingPassword123"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_get_current_user(
    client: AsyncClient,
    test_user: User,
) -> None:
    login_response = await client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "TestPassword123"},
    )
    token = login_response.json()["access_token"]

    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["username"] == test_user.username


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(client: AsyncClient) -> None:
    response = await client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_login_inactive_user(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    test_user.is_active = False
    database_session.add(test_user)
    await database_session.commit()

    response = await client.post(
        "/api/auth/login",
        json={"username": test_user.username, "password": "TestPassword123"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is disabled"
