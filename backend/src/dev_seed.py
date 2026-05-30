from dataclasses import dataclass
import os
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import hash_password
from src.devices.models import Device
from src.devices.service import hash_device_token
from src.doors.models import Door
from src.roles.models import Role
from src.users.models import User


DEV_ADMIN_USERNAME = "admin"
DEV_ADMIN_PASSWORD = "AdminPassword123"
DEV_ADMIN_FULL_NAME = "Development Admin"
DEV_ADMIN_EMAIL = "admin@example.test"
DEV_DOOR_ID = UUID("00000000-0000-4000-8000-000000000001")
DEV_DOOR_NAME = "Front Door"
DEV_DOOR_MQTT_ID = "front-door"
DEV_DEVICE_NAME = "dev-jetson"
DEV_DEVICE_TOKEN = "dev-device-token"


@dataclass(frozen=True)
class DevSeedResult:
    door_id: UUID
    device_token: str


@dataclass(frozen=True)
class DevSeedConfig:
    admin_username: str = DEV_ADMIN_USERNAME
    admin_password: str = DEV_ADMIN_PASSWORD
    admin_full_name: str = DEV_ADMIN_FULL_NAME
    admin_email: str | None = DEV_ADMIN_EMAIL
    door_id: str = str(DEV_DOOR_ID)
    device_token: str = DEV_DEVICE_TOKEN

    @classmethod
    def from_env(cls) -> "DevSeedConfig":
        return cls(
            admin_username=os.getenv("DEFAULT_ADMIN_USERNAME", DEV_ADMIN_USERNAME),
            admin_password=os.getenv("DEFAULT_ADMIN_PASSWORD", DEV_ADMIN_PASSWORD),
            admin_full_name=os.getenv("DEFAULT_ADMIN_FULL_NAME", DEV_ADMIN_FULL_NAME),
            admin_email=os.getenv("DEFAULT_ADMIN_EMAIL", DEV_ADMIN_EMAIL),
            door_id=os.getenv("DEV_DOOR_ID", str(DEV_DOOR_ID)),
            device_token=os.getenv("DEV_DEVICE_TOKEN", DEV_DEVICE_TOKEN),
        )


async def ensure_dev_seed(
    session: AsyncSession,
    config: DevSeedConfig | None = None,
) -> DevSeedResult:
    """Create deterministic local-development records without overwriting them."""

    config = config or DevSeedConfig.from_env()
    admin_username = config.admin_username.lower()
    requested_door_id = UUID(config.door_id)

    admin_role = (
        await session.exec(select(Role).where(Role.name == "admin"))
    ).one_or_none()
    if admin_role is None:
        raise RuntimeError("Admin role seed data is missing.")

    admin = (
        await session.exec(select(User).where(User.username == admin_username))
    ).one_or_none()
    if admin is None:
        session.add(
            User(
                username=admin_username,
                email=config.admin_email,
                password_hash=hash_password(config.admin_password),
                full_name=config.admin_full_name,
                role_id=admin_role.id,
                is_active=True,
            )
        )

    door = await session.get(Door, requested_door_id)
    if door is None:
        door = (
            await session.exec(
                select(Door).where(
                    or_(
                        col(Door.name) == DEV_DOOR_NAME,
                        col(Door.mqtt_id) == DEV_DOOR_MQTT_ID,
                    )
                )
            )
        ).first()
    if door is None:
        door = Door(
            id=requested_door_id,
            name=DEV_DOOR_NAME,
            mqtt_id=DEV_DOOR_MQTT_ID,
            location="Development",
            is_active=True,
        )
        session.add(door)
        await session.flush()

    device = (
        await session.exec(select(Device).where(Device.name == DEV_DEVICE_NAME))
    ).one_or_none()
    if device is None:
        device = (
            await session.exec(
                select(Device).where(
                    Device.token_hash == hash_device_token(config.device_token)
                )
            )
        ).one_or_none()
    if device is None:
        session.add(
            Device(
                name=DEV_DEVICE_NAME,
                door_id=door.id,
                token_hash=hash_device_token(config.device_token),
                is_active=True,
            )
        )
    else:
        device.name = DEV_DEVICE_NAME
        device.door_id = door.id
        device.token_hash = hash_device_token(config.device_token)
        device.is_active = True
        session.add(device)

    await session.commit()
    return DevSeedResult(door_id=door.id, device_token=config.device_token)
