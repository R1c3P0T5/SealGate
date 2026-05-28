from datetime import datetime
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.access_logs.models import AccessLog
from src.auth.utils import create_access_token
from src.doors.models import Door
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _grant_role_permission(
    session: AsyncSession,
    role: Role,
    permission_name: str,
) -> None:
    permission = (
        await session.exec(select(Permission).where(Permission.name == permission_name))
    ).one_or_none()
    if permission is None:
        permission = Permission(name=permission_name)
        session.add(permission)
        await session.flush()

    existing = (
        await session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        )
    ).one_or_none()
    if existing is None:
        session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await session.commit()


async def _create_door(session: AsyncSession, name: str = "front_gate") -> Door:
    door = Door(name=name, mqtt_id=name)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


async def _create_access_log(
    session: AsyncSession,
    *,
    door: Door,
    username: str | None = "alice",
    door_opened: bool = True,
) -> AccessLog:
    access_log = AccessLog(
        timestamp=datetime(2026, 5, 19, 8, 30, 0),
        door_id=door.id,
        user_id=uuid4(),
        username=username,
        confidence=0.91,
        door_opened=door_opened,
    )
    session.add(access_log)
    await session.commit()
    await session.refresh(access_log)
    return access_log


def test_access_logs_router_exposes_expected_routes() -> None:
    from src.access_logs.router import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert router.prefix == "/api/access-logs"
    assert ("/api/access-logs", ("GET",)) in routes


@pytest.mark.asyncio
async def test_list_access_logs_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/access-logs")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_access_logs_rejects_user_without_permission(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.get(
        "/api/access-logs",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


@pytest.mark.asyncio
async def test_list_access_logs_returns_logs_for_user_with_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
    test_user: User,
) -> None:
    await _grant_role_permission(database_session, seeded_roles["user"], "log:read")
    door = await _create_door(database_session)
    access_log = await _create_access_log(database_session, door=door)

    response = await client.get(
        "/api/access-logs",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["skip"] == 0
    assert data["limit"] == 10
    assert data["logs"] == [
        {
            "id": str(access_log.id),
            "timestamp": "2026-05-19T08:30:00Z",
            "door_id": str(door.id),
            "user_id": str(access_log.user_id),
            "username": "alice",
            "confidence": 0.91,
            "door_opened": True,
        }
    ]


@pytest.mark.asyncio
async def test_list_access_logs_supports_pagination(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
    test_user: User,
) -> None:
    await _grant_role_permission(database_session, seeded_roles["user"], "log:read")
    door = await _create_door(database_session)
    for index in range(3):
        await _create_access_log(
            database_session,
            door=door,
            username=f"user_{index}",
            door_opened=index % 2 == 0,
        )

    response = await client.get(
        "/api/access-logs?skip=1&limit=1",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["skip"] == 1
    assert data["limit"] == 1
    assert len(data["logs"]) == 1


def test_access_log_response_serializes_naive_utc_timestamp_with_z_suffix() -> None:
    from src.access_logs.schemas import AccessLogResponse

    access_log = AccessLog(
        timestamp=datetime(2026, 5, 19, 8, 30, 0),
        door_id=uuid4(),
        user_id=None,
        username=None,
        confidence=None,
        door_opened=False,
    )

    payload = AccessLogResponse.model_validate(access_log).model_dump(mode="json")

    assert payload["timestamp"] == "2026-05-19T08:30:00Z"
