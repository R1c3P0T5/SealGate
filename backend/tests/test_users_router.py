from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token, hash_password
from src.roles.models import Role
from src.users.models import User
from src.users.schemas import (
    UserListResponse,
    UserUpdateRequest,
)


async def create_user(
    session: AsyncSession,
    *,
    role_name: str = "user",
) -> User:
    role = (await session.exec(select(Role).where(Role.name == role_name))).one()
    user = User(
        username=f"user_{uuid4().hex[:12]}",
        email=f"{uuid4().hex[:12]}@example.com",
        password_hash="hash",
        full_name="Router User",
        role_id=role.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def test_users_router_exposes_expected_routes() -> None:
    from src.users.router import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert router.prefix == "/api/users"
    assert ("/api/users", ("GET",)) in routes
    assert ("/api/users/{user_id}", ("GET",)) in routes
    assert ("/api/users/{user_id}", ("PUT",)) in routes
    assert ("/api/users/{user_id}", ("DELETE",)) in routes
    assert ("/api/users/{user_id}/active", ("PUT",)) in routes


def test_main_app_includes_users_routes() -> None:
    from main import app

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert ("/api/users", ("GET",)) in routes
    assert ("/api/users/{user_id}", ("GET",)) in routes


@pytest.mark.asyncio
async def test_get_user_endpoint_returns_user_response(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.router import get_user

    user = await create_user(database_session)

    response = await get_user(user.id, database_session, user)

    assert response.id == user.id
    assert response.username == user.username


@pytest.mark.asyncio
async def test_update_user_endpoint_returns_updated_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.router import update_user_profile

    user = await create_user(database_session)

    response = await update_user_profile(
        user.id,
        UserUpdateRequest(full_name="Updated User"),
        database_session,
        user,
    )

    assert response.full_name == "Updated User"


@pytest.mark.asyncio
async def test_delete_user_endpoint_returns_none(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.router import delete_user_profile

    user = await create_user(database_session)

    assert await delete_user_profile(user.id, database_session, user) is None


@pytest.mark.asyncio
async def test_list_users_endpoint_returns_paginated_response(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.router import list_users_endpoint

    admin = await create_user(database_session, role_name="admin")
    await create_user(database_session)

    response = await list_users_endpoint(database_session, admin, skip=0, limit=50)

    assert isinstance(response, UserListResponse)
    assert response.total >= 2
    assert response.limit == 50


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_active_user(
    session: AsyncSession,
    seeded_roles: dict[str, Role],
    *,
    password: str = "UserPass123!",
    role_name: str = "user",
) -> tuple[User, str]:
    role = seeded_roles[role_name]
    user = User(
        username=f"pw_user_{uuid4().hex[:10]}",
        email=f"pw_{uuid4().hex[:10]}@example.com",
        password_hash=hash_password(password),
        full_name="PW Test User",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user.id)


@pytest.mark.asyncio
async def test_change_password_self_success(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user, token = await _create_active_user(database_session, seeded_roles)

    response = await client.put(
        f"/api/users/{user.id}/password",
        json={"current_password": "UserPass123!", "new_password": "NewSecurePass456!"},
        headers=_auth(token),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_self_wrong_current_returns_401(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user, token = await _create_active_user(database_session, seeded_roles)

    response = await client.put(
        f"/api/users/{user.id}/password",
        json={"current_password": "WrongPass!", "new_password": "NewPass456!"},
        headers=_auth(token),
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_change_password_self_missing_current_returns_400(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user, token = await _create_active_user(database_session, seeded_roles)

    response = await client.put(
        f"/api/users/{user.id}/password",
        json={"new_password": "NewPass456!"},
        headers=_auth(token),
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_password_admin_no_current_password_needed(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    target, _ = await _create_active_user(database_session, seeded_roles)
    _admin, admin_token = await _create_active_user(
        database_session, seeded_roles, role_name="admin"
    )

    response = await client.put(
        f"/api/users/{target.id}/password",
        json={"new_password": "AdminSetPass456!"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_change_password_requires_auth(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user, _ = await _create_active_user(database_session, seeded_roles)

    response = await client.put(
        f"/api/users/{user.id}/password",
        json={"current_password": "UserPass123!", "new_password": "NewPass456!"},
    )

    assert response.status_code == 401
