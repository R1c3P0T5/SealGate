from uuid import UUID

from fastapi import Request, WebSocket

from src.core.database import SessionDep
from src.core.exceptions import DoorNotFoundError
from src.devices.service import get_device_by_token_hash, hash_device_token
from src.doors.models import Door
from src.doors.service import get_door_by_id


class DeviceAuthError(Exception):
    detail = "Invalid device token"


class DeviceDoorInactiveError(DeviceAuthError):
    detail = "Door is inactive"


def _device_token(scope: Request | WebSocket) -> str | None:
    return scope.headers.get("x-device-token")


async def get_device_door(
    scope: Request | WebSocket,
    door_id: UUID,
    session: SessionDep,
) -> Door:
    token = _device_token(scope)
    if token is None:
        raise DeviceAuthError()

    device = await get_device_by_token_hash(hash_device_token(token), session)
    if device is None or not device.is_active:
        raise DeviceAuthError()
    if device.door_id != door_id:
        raise DeviceAuthError()

    try:
        door = await get_door_by_id(door_id, session)
    except DoorNotFoundError:
        raise DeviceAuthError() from None
    if not door.is_active:
        raise DeviceDoorInactiveError()
    return door
