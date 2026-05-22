from uuid import uuid4

import pytest
from starlette.requests import Request
from sqlmodel.ext.asyncio.session import AsyncSession

from src.devices.auth import (
    DeviceAuthError,
    DeviceDoorInactiveError,
    get_device_door,
)
from src.devices.models import Device
from src.devices.service import hash_device_token
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
async def test_device_auth_accepts_matching_token_and_door(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(
            name="front-door-device",
            door_id=door.id,
            token_hash=hash_device_token("device-token"),
        )
    )
    await database_session.commit()

    assert (
        await get_device_door(_request("device-token"), door.id, database_session)
    ).id == door.id


@pytest.mark.asyncio
async def test_device_auth_rejects_missing_token(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    with pytest.raises(DeviceAuthError):
        await get_device_door(_request(), door.id, database_session)


@pytest.mark.asyncio
async def test_device_auth_rejects_wrong_token(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(
            name="front-door-device",
            door_id=door.id,
            token_hash=hash_device_token("device-token"),
        )
    )
    await database_session.commit()

    with pytest.raises(DeviceAuthError):
        await get_device_door(_request("wrong-token"), door.id, database_session)


@pytest.mark.asyncio
async def test_device_auth_rejects_wrong_door(
    database_session: AsyncSession,
) -> None:
    configured_door = await _create_door(database_session)
    other_door = await _create_door(database_session)
    database_session.add(
        Device(
            name="front-door-device",
            door_id=configured_door.id,
            token_hash=hash_device_token("device-token"),
        )
    )
    await database_session.commit()

    with pytest.raises(DeviceAuthError):
        await get_device_door(_request("device-token"), other_door.id, database_session)


@pytest.mark.asyncio
async def test_device_auth_rejects_inactive_device(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(
            name="front-door-device",
            door_id=door.id,
            token_hash=hash_device_token("device-token"),
            is_active=False,
        )
    )
    await database_session.commit()

    with pytest.raises(DeviceAuthError):
        await get_device_door(_request("device-token"), door.id, database_session)


@pytest.mark.asyncio
async def test_device_auth_distinguishes_inactive_door(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session, active=False)
    database_session.add(
        Device(
            name="front-door-device",
            door_id=door.id,
            token_hash=hash_device_token("device-token"),
        )
    )
    await database_session.commit()

    with pytest.raises(DeviceDoorInactiveError):
        await get_device_door(_request("device-token"), door.id, database_session)
