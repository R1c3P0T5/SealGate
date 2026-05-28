from datetime import datetime
from unittest.mock import ANY
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

from main import create_app
from src.access_logs.schemas import AccessLogResponse
from src.auth.utils import create_access_token
from src.core.database import get_session
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


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


def _test_app(database_session: AsyncSession) -> FastAPI:
    app = create_app()

    async def override_get_session() -> AsyncSession:
        return database_session

    app.dependency_overrides[get_session] = override_get_session

    @app.post("/__test_publish_access_event")
    async def publish_access_event() -> dict[str, bool]:
        event = AccessLogResponse(
            id=uuid4(),
            timestamp=datetime(2026, 5, 20, 10, 0, 0),
            door_id=uuid4(),
            user_id=uuid4(),
            username="alice",
            confidence=0.91,
            door_opened=True,
        )
        await app.state.access_event_broker.publish(event)
        return {"ok": True}

    return app


def _expected_event() -> dict[str, object]:
    return {
        "id": ANY,
        "timestamp": "2026-05-20T10:00:00Z",
        "door_id": ANY,
        "user_id": ANY,
        "username": "alice",
        "confidence": 0.91,
        "door_opened": True,
    }


def _connect_error_code(
    client: TestClient,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> int:
    with client.websocket_connect(path, headers=headers or {}) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()
    return int(exc_info.value.code)


@pytest.mark.asyncio
async def test_access_event_websocket_rejects_missing_token(
    database_session: AsyncSession,
) -> None:
    client = TestClient(_test_app(database_session))

    assert _connect_error_code(client, "/ws/events/access") == 1008


@pytest.mark.asyncio
async def test_access_event_websocket_rejects_user_without_permission(
    database_session: AsyncSession,
    test_user: User,
) -> None:
    client = TestClient(_test_app(database_session))
    token = create_access_token(test_user.id)

    assert (
        _connect_error_code(client, f"/ws/events/access?access_token={token}") == 1008
    )


@pytest.mark.asyncio
async def test_access_event_websocket_receives_published_event_with_query_token(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
    test_user: User,
) -> None:
    await _grant_role_permission(database_session, seeded_roles["user"], "log:read")
    app = _test_app(database_session)
    client = TestClient(app)
    token = create_access_token(test_user.id)

    with client.websocket_connect(f"/ws/events/access?access_token={token}") as ws:
        response = client.post("/__test_publish_access_event")
        assert response.status_code == 200

        assert ws.receive_json() == _expected_event()


@pytest.mark.asyncio
async def test_access_event_websocket_accepts_bearer_header(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
    test_user: User,
) -> None:
    await _grant_role_permission(database_session, seeded_roles["user"], "log:read")
    client = TestClient(_test_app(database_session))
    token = create_access_token(test_user.id)

    with client.websocket_connect(
        "/ws/events/access",
        headers={"Authorization": f"Bearer {token}"},
    ) as ws:
        response = client.post("/__test_publish_access_event")
        assert response.status_code == 200

        assert ws.receive_json() == _expected_event()
