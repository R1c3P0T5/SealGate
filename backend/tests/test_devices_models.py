import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.devices.models import Device
from src.doors.models import Door


async def _create_door(session: AsyncSession, name: str = "device_door") -> Door:
    door = Door(name=name, mqtt_id=name)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


def test_device_table_is_registered_in_metadata() -> None:
    table = SQLModel.metadata.tables["device"]

    assert "device" in SQLModel.metadata.tables
    assert "id" in table.columns
    assert "name" in table.columns
    assert "door_id" in table.columns
    assert "token_hash" in table.columns
    assert "is_active" in table.columns
    assert "created_at" in table.columns
    assert "updated_at" in table.columns
    assert table.c.door_id.foreign_keys
    assert next(iter(table.c.door_id.foreign_keys)).ondelete == "RESTRICT"
    assert table.c.door_id.index is True


def test_device_model_requires_door_id() -> None:
    with pytest.raises(ValidationError):
        Device.model_validate({"name": "front-door-device", "token_hash": "a" * 64})


@pytest.mark.asyncio
async def test_create_device_persists_required_fields(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device = Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)

    database_session.add(device)
    await database_session.commit()
    await database_session.refresh(device)

    assert device.id is not None
    assert device.door_id == door.id
    assert device.is_active is True
    assert device.created_at is not None
    assert device.updated_at is not None


@pytest.mark.asyncio
async def test_device_name_is_unique(database_session: AsyncSession) -> None:
    door = await _create_door(database_session)
    database_session.add(
        Device(name="front-door-device", door_id=door.id, token_hash="a" * 64)
    )
    await database_session.commit()
    database_session.add(
        Device(name="front-door-device", door_id=door.id, token_hash="b" * 64)
    )

    with pytest.raises(IntegrityError):
        await database_session.commit()
    await database_session.rollback()


@pytest.mark.asyncio
async def test_device_token_hash_is_unique(database_session: AsyncSession) -> None:
    door = await _create_door(database_session)
    database_session.add(Device(name="device-a", door_id=door.id, token_hash="a" * 64))
    await database_session.commit()
    database_session.add(Device(name="device-b", door_id=door.id, token_hash="a" * 64))

    with pytest.raises(IntegrityError):
        await database_session.commit()
    await database_session.rollback()
