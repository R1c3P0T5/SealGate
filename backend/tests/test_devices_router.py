from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
from src.devices.models import Device
from src.devices.service import hash_device_token
from src.doors.models import Door
from src.users.models import User


async def _create_door(session: AsyncSession, name: str = "device_door") -> Door:
    door = Door(name=name, mqtt_id=name)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_devices_router_exposes_expected_routes() -> None:
    from src.devices.router import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert router.prefix == "/api/devices"
    assert ("/api/devices", ("GET",)) in routes
    assert ("/api/devices", ("POST",)) in routes
    assert ("/api/devices/{device_id}", ("GET",)) in routes
    assert ("/api/devices/{device_id}", ("PUT",)) in routes
    assert ("/api/devices/{device_id}", ("DELETE",)) in routes
    assert ("/api/devices/{device_id}/rotate-token", ("POST",)) in routes


@pytest.mark.asyncio
async def test_list_devices_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/devices")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_devices_rejects_user_without_device_manage(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.get(
        "/api/devices",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_device_returns_one_time_token_for_admin(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)

    response = await client.post(
        "/api/devices",
        json={"name": "front-door-device", "door_id": str(door.id)},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "front-door-device"
    assert data["door_id"] == str(door.id)
    assert data["is_active"] is True
    assert data["token"]
    assert "token_hash" not in data


@pytest.mark.asyncio
async def test_create_device_rejects_missing_door(
    client: AsyncClient,
    test_admin: User,
) -> None:
    response = await client.post(
        "/api/devices",
        json={"name": "front-door-device", "door_id": str(uuid4())},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Door not found"


@pytest.mark.asyncio
async def test_create_device_rejects_duplicate_name(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    )
    await database_session.commit()

    response = await client.post(
        "/api/devices",
        json={"name": "front-door-device", "door_id": str(door.id)},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Device name already in use"


@pytest.mark.asyncio
async def test_list_devices_omits_tokens(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    )
    await database_session.commit()

    response = await client.get(
        "/api/devices",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["skip"] == 0
    assert data["limit"] == 10
    assert data["devices"][0]["name"] == "front-door-device"
    assert "token" not in data["devices"][0]
    assert "token_hash" not in data["devices"][0]


@pytest.mark.asyncio
async def test_get_device_omits_tokens(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    device = Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    response = await client.get(
        f"/api/devices/{device.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(device.id)
    assert "token" not in data
    assert "token_hash" not in data


@pytest.mark.asyncio
async def test_update_device_changes_fields_without_token(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    other_door = await _create_door(database_session, name="other_device_door")
    device = Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    response = await client.put(
        f"/api/devices/{device.id}",
        json={
            "name": "renamed-device",
            "door_id": str(other_door.id),
            "is_active": False,
        },
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "renamed-device"
    assert data["door_id"] == str(other_door.id)
    assert data["is_active"] is False
    assert "token" not in data
    assert "token_hash" not in data


@pytest.mark.asyncio
async def test_update_device_rejects_missing_door(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    device = Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    response = await client.put(
        f"/api/devices/{device.id}",
        json={"door_id": str(uuid4())},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Door not found"


@pytest.mark.asyncio
async def test_rotate_device_token_returns_new_one_time_token(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    old_token = "old-token"
    device = Device(
        name="front-door-device",
        door_id=door.id,
        token_hash=hash_device_token(old_token),
    )
    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    response = await client.post(
        f"/api/devices/{device.id}/rotate-token",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["token"]
    assert data["token"] != old_token
    assert "token_hash" not in data


@pytest.mark.asyncio
async def test_delete_device_removes_device(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    door = await _create_door(database_session)
    device = Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    response = await client.delete(
        f"/api/devices/{device.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 204
    assert await database_session.get(Device, device.id) is None
