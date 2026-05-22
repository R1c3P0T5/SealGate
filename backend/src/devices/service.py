import hashlib
import secrets
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import (
    DeviceNameAlreadyExistsError,
    DeviceNotFoundError,
    DeviceTokenCollisionError,
)
from src.core.utils import utc_now_naive
from src.devices.models import Device
from src.devices.schemas import DeviceCreateRequest, DeviceResponse, DeviceUpdateRequest
from src.doors.service import get_door_by_id


# Token collisions are practically impossible; one retry avoids surfacing a transient hash collision as user error.
_TOKEN_HASH_COLLISION_ATTEMPTS = 2


def generate_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def to_device_response(device: Device) -> DeviceResponse:
    return DeviceResponse(
        id=device.id,
        name=device.name,
        door_id=device.door_id,
        is_active=device.is_active,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


def _integrity_error_text(exc: IntegrityError) -> str:
    return str(exc.orig).lower()


def _is_token_hash_collision(exc: IntegrityError) -> bool:
    return "token_hash" in _integrity_error_text(exc)


def _raise_integrity_error(exc: IntegrityError) -> None:
    if _is_token_hash_collision(exc):
        raise DeviceTokenCollisionError() from exc
    raise DeviceNameAlreadyExistsError() from exc


async def get_device_by_id(device_id: UUID, session: AsyncSession) -> Device:
    device = await session.get(Device, device_id)
    if device is None:
        raise DeviceNotFoundError()
    return device


async def get_device_by_token_hash(
    token_hash: str,
    session: AsyncSession,
) -> Device | None:
    return (
        await session.exec(select(Device).where(Device.token_hash == token_hash))
    ).one_or_none()


async def list_devices(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> tuple[int, list[Device]]:
    total = (await session.exec(select(func.count()).select_from(Device))).one()
    devices = list((await session.exec(select(Device).offset(skip).limit(limit))).all())
    return total, devices


async def create_device(
    request: DeviceCreateRequest,
    session: AsyncSession,
) -> tuple[Device, str]:
    await get_door_by_id(request.door_id, session)

    last_token = ""
    last_collision: IntegrityError | None = None
    for _ in range(_TOKEN_HASH_COLLISION_ATTEMPTS):
        token = generate_device_token()
        device = Device(
            name=request.name,
            door_id=request.door_id,
            token_hash=hash_device_token(token),
            is_active=request.is_active,
        )
        session.add(device)
        try:
            await session.commit()
            await session.refresh(device)
        except IntegrityError as exc:
            await session.rollback()
            if _is_token_hash_collision(exc):
                last_token = token
                last_collision = exc
                continue
            _raise_integrity_error(exc)
        else:
            return device, token

    if last_collision is not None and last_token:
        raise DeviceTokenCollisionError() from last_collision
    raise DeviceTokenCollisionError()


async def update_device(
    device_id: UUID,
    request: DeviceUpdateRequest,
    session: AsyncSession,
) -> Device:
    device = await get_device_by_id(device_id, session)

    if request.name is not None:
        device.name = request.name
    if request.door_id is not None:
        await get_door_by_id(request.door_id, session)
        device.door_id = request.door_id
    if request.is_active is not None:
        device.is_active = request.is_active
    device.updated_at = utc_now_naive()

    session.add(device)
    try:
        await session.commit()
        await session.refresh(device)
    except IntegrityError as exc:
        await session.rollback()
        _raise_integrity_error(exc)
    return device


async def delete_device(device_id: UUID, session: AsyncSession) -> None:
    device = await get_device_by_id(device_id, session)
    await session.delete(device)
    await session.commit()


async def rotate_device_token(
    device_id: UUID,
    session: AsyncSession,
) -> tuple[Device, str]:
    device = await get_device_by_id(device_id, session)

    last_collision: IntegrityError | None = None
    for _ in range(_TOKEN_HASH_COLLISION_ATTEMPTS):
        token = generate_device_token()
        device.token_hash = hash_device_token(token)
        device.updated_at = utc_now_naive()
        session.add(device)
        try:
            await session.commit()
            await session.refresh(device)
        except IntegrityError as exc:
            await session.rollback()
            if _is_token_hash_collision(exc):
                last_collision = exc
                device = await get_device_by_id(device_id, session)
                continue
            _raise_integrity_error(exc)
        else:
            return device, token

    if last_collision is not None:
        raise DeviceTokenCollisionError() from last_collision
    raise DeviceTokenCollisionError()
