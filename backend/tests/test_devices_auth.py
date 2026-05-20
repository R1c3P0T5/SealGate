from uuid import uuid4

import pytest
from starlette.requests import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings
from src.devices.auth import (
    DeviceDoorInactiveError,
    get_configured_device_door,
    is_configured_device_for_door,
)
from src.doors.models import Door


def _request(token: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if token is not None:
        headers.append((b"x-device-token", token.encode()))
    return Request({"type": "http", "headers": headers})


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


@pytest.mark.asyncio
async def test_configured_device_auth_accepts_matching_token_and_door(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door = await _create_door(database_session)
    monkeypatch.setenv("JETSON_DEVICE_TOKEN", "device-token")
    monkeypatch.setenv("JETSON_DEVICE_DOOR_ID", str(door.id))
    get_settings.cache_clear()

    assert await is_configured_device_for_door(
        _request("device-token"), door.id, database_session
    )
    assert (
        await get_configured_device_door(
            _request("device-token"), door.id, database_session
        )
    ).id == door.id


@pytest.mark.asyncio
async def test_configured_device_auth_rejects_missing_server_config(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    assert not await is_configured_device_for_door(
        _request("device-token"), door.id, database_session
    )


@pytest.mark.asyncio
async def test_configured_device_auth_rejects_wrong_token(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door = await _create_door(database_session)
    monkeypatch.setenv("JETSON_DEVICE_TOKEN", "device-token")
    monkeypatch.setenv("JETSON_DEVICE_DOOR_ID", str(door.id))
    get_settings.cache_clear()

    assert not await is_configured_device_for_door(
        _request("wrong-token"), door.id, database_session
    )


@pytest.mark.asyncio
async def test_configured_device_auth_rejects_wrong_door(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_door = await _create_door(database_session)
    other_door = await _create_door(database_session)
    monkeypatch.setenv("JETSON_DEVICE_TOKEN", "device-token")
    monkeypatch.setenv("JETSON_DEVICE_DOOR_ID", str(configured_door.id))
    get_settings.cache_clear()

    assert not await is_configured_device_for_door(
        _request("device-token"), other_door.id, database_session
    )


@pytest.mark.asyncio
async def test_configured_device_auth_distinguishes_inactive_door(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door = await _create_door(database_session, active=False)
    monkeypatch.setenv("JETSON_DEVICE_TOKEN", "device-token")
    monkeypatch.setenv("JETSON_DEVICE_DOOR_ID", str(door.id))
    get_settings.cache_clear()

    with pytest.raises(DeviceDoorInactiveError):
        await get_configured_device_door(
            _request("device-token"), door.id, database_session
        )
    assert not await is_configured_device_for_door(
        _request("device-token"), door.id, database_session
    )
