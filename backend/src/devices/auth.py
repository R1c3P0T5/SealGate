import logging
import secrets
from uuid import UUID

from fastapi import Request, WebSocket

from src.core.config import get_settings
from src.core.database import SessionDep
from src.core.exceptions import DoorNotFoundError
from src.doors.models import Door
from src.doors.service import get_door_by_id

logger = logging.getLogger(__name__)


class DeviceAuthError(Exception):
    detail = "Invalid device token"


class DeviceDoorInactiveError(DeviceAuthError):
    detail = "Door is inactive"


def _device_token(scope: Request | WebSocket) -> str | None:
    return scope.headers.get("x-device-token")


async def get_configured_device_door(
    scope: Request | WebSocket,
    door_id: UUID,
    session: SessionDep,
) -> Door:
    settings = get_settings()
    if not settings.JETSON_DEVICE_TOKEN or settings.JETSON_DEVICE_DOOR_ID is None:
        logger.warning("Jetson device token is not configured")
        raise DeviceAuthError()
    if door_id != settings.JETSON_DEVICE_DOOR_ID:
        raise DeviceAuthError()

    token = _device_token(scope)
    if token is None:
        raise DeviceAuthError()
    if not secrets.compare_digest(token, settings.JETSON_DEVICE_TOKEN):
        raise DeviceAuthError()

    try:
        door = await get_door_by_id(door_id, session)
    except DoorNotFoundError:
        raise DeviceAuthError() from None
    if not door.is_active:
        raise DeviceDoorInactiveError()
    return door


async def is_configured_device_for_door(
    scope: Request | WebSocket,
    door_id: UUID,
    session: SessionDep,
) -> bool:
    try:
        await get_configured_device_door(scope, door_id, session)
    except DeviceAuthError:
        return False
    return True
