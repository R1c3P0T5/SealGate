import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import verify_password
from src.devices.models import Device
from src.devices.service import hash_device_token
from src.doors.models import Door
from src.roles.models import Role
from src.users.models import User

pytestmark = pytest.mark.asyncio


async def _count(session: AsyncSession, model: type) -> int:
    return len(list((await session.exec(select(model))).all()))


async def test_ensure_dev_seed_creates_reusable_admin_door_and_device(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.dev_seed import (
        DEV_ADMIN_PASSWORD,
        DEV_DEVICE_TOKEN,
        DEV_DOOR_ID,
        DEV_DOOR_NAME,
        ensure_dev_seed,
    )

    result = await ensure_dev_seed(database_session)

    admin = (
        await database_session.exec(select(User).where(User.username == "admin"))
    ).one()
    door = await database_session.get(Door, DEV_DOOR_ID)
    device = (
        await database_session.exec(select(Device).where(Device.name == "dev-jetson"))
    ).one()

    assert result.door_id == DEV_DOOR_ID
    assert result.device_token == DEV_DEVICE_TOKEN
    assert admin.role_id == seeded_roles["admin"].id
    assert admin.is_active is True
    assert verify_password(DEV_ADMIN_PASSWORD, admin.password_hash)
    assert door is not None
    assert door.name == DEV_DOOR_NAME
    assert device.door_id == DEV_DOOR_ID
    assert device.token_hash == hash_device_token(DEV_DEVICE_TOKEN)


async def test_ensure_dev_seed_uses_configured_credentials(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.dev_seed import DevSeedConfig, ensure_dev_seed

    door_id = "11111111-1111-4111-8111-111111111111"
    config = DevSeedConfig(
        admin_username="owner",
        admin_password="OwnerPassword123",
        admin_full_name="Owner Admin",
        admin_email="owner@example.test",
        door_id=door_id,
        device_token="owner-device-token",
    )

    result = await ensure_dev_seed(database_session, config)

    admin = (
        await database_session.exec(select(User).where(User.username == "owner"))
    ).one()
    door = await database_session.get(Door, result.door_id)
    device = (
        await database_session.exec(select(Device).where(Device.name == "dev-jetson"))
    ).one()

    assert str(result.door_id) == door_id
    assert result.device_token == "owner-device-token"
    assert admin.full_name == "Owner Admin"
    assert verify_password("OwnerPassword123", admin.password_hash)
    assert door is not None
    assert device.door_id == result.door_id
    assert device.token_hash == hash_device_token("owner-device-token")


async def test_ensure_dev_seed_is_idempotent(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.dev_seed import ensure_dev_seed

    await ensure_dev_seed(database_session)
    await ensure_dev_seed(database_session)

    assert await _count(database_session, User) == 1
    assert await _count(database_session, Door) == 1
    assert await _count(database_session, Device) == 1


async def test_ensure_dev_seed_reuses_partial_dev_door_and_repairs_device(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.dev_seed import (
        DEV_DEVICE_NAME,
        DEV_DEVICE_TOKEN,
        DEV_DOOR_MQTT_ID,
        DEV_DOOR_NAME,
        ensure_dev_seed,
    )

    existing_door = Door(name=DEV_DOOR_NAME, mqtt_id=DEV_DOOR_MQTT_ID)
    other_door = Door(name="Other Door", mqtt_id="other-door")
    database_session.add(existing_door)
    database_session.add(other_door)
    await database_session.flush()
    database_session.add(
        Device(
            name=DEV_DEVICE_NAME,
            door_id=other_door.id,
            token_hash=hash_device_token("stale-token"),
        )
    )
    await database_session.commit()

    result = await ensure_dev_seed(database_session)

    device = (
        await database_session.exec(
            select(Device).where(Device.name == DEV_DEVICE_NAME)
        )
    ).one()
    assert result.door_id == existing_door.id
    assert device.door_id == existing_door.id
    assert device.token_hash == hash_device_token(DEV_DEVICE_TOKEN)


async def test_ensure_dev_seed_reuses_existing_device_token(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.dev_seed import DEV_DEVICE_NAME, DEV_DEVICE_TOKEN, ensure_dev_seed

    door = Door(name="Existing Door", mqtt_id="existing-door")
    database_session.add(door)
    await database_session.flush()
    database_session.add(
        Device(
            name="existing-device",
            door_id=door.id,
            token_hash=hash_device_token(DEV_DEVICE_TOKEN),
        )
    )
    await database_session.commit()

    result = await ensure_dev_seed(database_session)

    devices = list((await database_session.exec(select(Device))).all())
    assert len(devices) == 1
    assert devices[0].name == DEV_DEVICE_NAME
    assert devices[0].door_id == result.door_id
    assert devices[0].token_hash == hash_device_token(DEV_DEVICE_TOKEN)
