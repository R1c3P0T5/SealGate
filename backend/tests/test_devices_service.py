from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import (
    DeviceNameAlreadyExistsError,
    DeviceTokenCollisionError,
    DoorNotFoundError,
)
from src.devices.models import Device
from src.devices.schemas import DeviceCreateRequest, DeviceResponse, DeviceUpdateRequest
from src.devices.service import (
    create_device,
    get_device_by_token_hash,
    hash_device_token,
    rotate_device_token,
    to_device_response,
    update_device,
)
from src.doors.models import Door


async def _create_door(session: AsyncSession, name: str = "device_door") -> Door:
    door = Door(name=name, mqtt_id=name)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


@pytest.mark.asyncio
async def test_create_device_returns_plaintext_token_and_stores_hash(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    device, token = await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )

    assert token
    assert device.token_hash == hash_device_token(token)
    assert device.token_hash != token
    assert device.door_id == door.id
    assert device.is_active is True


def test_device_response_does_not_include_token_hash() -> None:
    device = Device(name="front-door-device", door_id=uuid4(), token_hash="a" * 64)

    response = to_device_response(device)

    assert isinstance(response, DeviceResponse)
    dumped = response.model_dump()
    assert "token_hash" not in dumped
    assert "token" not in dumped


def test_device_create_requires_door_id() -> None:
    with pytest.raises(ValidationError):
        DeviceCreateRequest.model_validate({"name": "front-door-device"})


@pytest.mark.asyncio
async def test_create_device_rejects_missing_door(
    database_session: AsyncSession,
) -> None:
    with pytest.raises(DoorNotFoundError):
        await create_device(
            DeviceCreateRequest(name="front-door-device", door_id=uuid4()),
            database_session,
        )


@pytest.mark.asyncio
async def test_get_device_by_token_hash_returns_device(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device, token = await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )

    found = await get_device_by_token_hash(hash_device_token(token), database_session)

    assert found is not None
    assert found.id == device.id


@pytest.mark.asyncio
async def test_get_device_by_token_hash_returns_none_for_wrong_token(
    database_session: AsyncSession,
) -> None:
    assert (
        await get_device_by_token_hash(hash_device_token("wrong"), database_session)
        is None
    )


@pytest.mark.asyncio
async def test_rotate_device_token_invalidates_old_token(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device, old_token = await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )

    rotated, new_token = await rotate_device_token(device.id, database_session)

    assert rotated.id == device.id
    assert new_token != old_token
    assert (
        await get_device_by_token_hash(hash_device_token(old_token), database_session)
        is None
    )
    found = await get_device_by_token_hash(
        hash_device_token(new_token), database_session
    )
    assert found is not None
    assert found.id == device.id


@pytest.mark.asyncio
async def test_update_device_updates_fields_and_updated_at(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    other_door = await _create_door(database_session, name="other_device_door")
    device, _ = await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )
    original_updated_at = device.updated_at
    device.updated_at = original_updated_at - timedelta(seconds=5)
    await database_session.commit()

    updated = await update_device(
        device.id,
        DeviceUpdateRequest(
            name="renamed-device",
            door_id=other_door.id,
            is_active=False,
        ),
        database_session,
    )

    assert updated.name == "renamed-device"
    assert updated.door_id == other_door.id
    assert updated.is_active is False
    assert updated.updated_at > original_updated_at - timedelta(seconds=5)


@pytest.mark.asyncio
async def test_rotate_device_token_updates_updated_at(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device, _ = await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )
    original_updated_at = device.updated_at
    device.updated_at = original_updated_at - timedelta(seconds=5)
    await database_session.commit()

    rotated, _ = await rotate_device_token(device.id, database_session)

    assert rotated.updated_at > original_updated_at - timedelta(seconds=5)


@pytest.mark.asyncio
async def test_duplicate_device_name_returns_business_error(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    await create_device(
        DeviceCreateRequest(name="front-door-device", door_id=door.id),
        database_session,
    )

    with pytest.raises(DeviceNameAlreadyExistsError):
        await create_device(
            DeviceCreateRequest(name="front-door-device", door_id=door.id),
            database_session,
        )


@pytest.mark.asyncio
async def test_token_hash_collision_retries_before_error(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.devices.service as service

    door = await _create_door(database_session)
    await create_device(
        DeviceCreateRequest(name="existing-device", door_id=door.id),
        database_session,
    )
    existing_hash = await get_device_by_token_hash(
        hash_device_token("collision"), database_session
    )
    assert existing_hash is None
    database_session.add(
        Device(
            name="hash-owner",
            door_id=door.id,
            token_hash=hash_device_token("collision"),
        )
    )
    await database_session.commit()

    tokens = iter(["collision", "unique"])
    monkeypatch.setattr(service, "generate_device_token", lambda: next(tokens))

    device, token = await create_device(
        DeviceCreateRequest(name="new-device", door_id=door.id),
        database_session,
    )

    assert token == "unique"
    assert device.token_hash == hash_device_token("unique")


@pytest.mark.asyncio
async def test_token_hash_collision_after_retry_returns_server_error(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.devices.service as service

    door = await _create_door(database_session)
    database_session.add(
        Device(
            name="hash-owner",
            door_id=door.id,
            token_hash=hash_device_token("collision"),
        )
    )
    await database_session.commit()
    monkeypatch.setattr(service, "generate_device_token", lambda: "collision")

    with pytest.raises(DeviceTokenCollisionError):
        await create_device(
            DeviceCreateRequest(name="new-device", door_id=door.id),
            database_session,
        )
