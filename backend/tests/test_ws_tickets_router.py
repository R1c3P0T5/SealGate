from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
from src.doors.models import Door
from src.users.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _create_door(session: AsyncSession, *, active: bool = True) -> Door:
    door = Door(
        name=f"door_{uuid4().hex[:12]}",
        mqtt_id=f"door_{uuid4().hex[:12]}",
        is_active=active,
    )
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


def test_ws_tickets_router_exposes_expected_routes() -> None:
    from src.ws_tickets.router import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert router.prefix == "/api/ws-tickets"
    assert ("/api/ws-tickets/camera-preview", ("POST",)) in routes


@pytest.mark.asyncio
async def test_create_camera_preview_ticket_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(uuid4())},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_camera_preview_ticket_rejects_user_without_permission(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(uuid4())},
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Permission denied"


@pytest.mark.asyncio
async def test_create_camera_preview_ticket_returns_404_for_missing_door(
    client: AsyncClient,
    test_admin: User,
) -> None:
    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(uuid4())},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Door not found"


@pytest.mark.asyncio
async def test_create_camera_preview_ticket_rejects_inactive_door(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session, active=False)

    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(door.id)},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Door is inactive"


@pytest.mark.asyncio
async def test_create_camera_preview_ticket_returns_one_time_ticket(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)

    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(door.id)},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["ticket"], str)
    assert isinstance(data["expires_at"], str)


@pytest.mark.asyncio
async def test_ticket_from_rest_works_on_ws_preview(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    from fastapi.testclient import TestClient
    from main import app as main_app

    door = await _create_door(database_session)

    response = await client.post(
        "/api/ws-tickets/camera-preview",
        json={"door_id": str(door.id)},
        headers=_auth(create_access_token(test_admin.id)),
    )
    assert response.status_code == 200
    ticket = response.json()["ticket"]

    ws_client = TestClient(main_app)
    with ws_client.websocket_connect(f"/ws/camera/{door.id}/preview?ticket={ticket}"):
        pass
