import logging
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Path, WebSocket
from starlette.websockets import WebSocketDisconnect

from src.camera.broker import CameraFrameBroker
from src.core.config import get_settings
from src.core.database import SessionDep
from src.core.exceptions import DoorNotFoundError
from src.devices.auth import (
    DeviceAuthError,
    get_configured_device_door,
)
from src.doors.service import get_door_by_id
from src.ws_tickets.store import WebSocketTicketStore

router = APIRouter(tags=["camera"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/camera/{door_id}/push")
async def camera_push_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID this producer serves.")],
    websocket: WebSocket,
    session: SessionDep,
) -> None:
    """Jetson producer：送出 binary JPEG 影格，接收 start/stop 控制。"""
    try:
        await get_configured_device_door(websocket, door_id, session)
    except DeviceAuthError as exc:
        await websocket.accept()
        await websocket.close(code=1008, reason=exc.detail)
        return

    broker = cast(CameraFrameBroker, websocket.app.state.camera_frame_broker)
    max_frame_bytes = get_settings().CAMERA_PREVIEW_MAX_FRAME_BYTES
    await websocket.accept()
    await broker.connect_producer(str(door_id), websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            frame = message.get("bytes")
            if frame is None:
                continue
            if len(frame) > max_frame_bytes:
                await websocket.close(code=1009)
                break
            await broker.relay_frame(str(door_id), frame, websocket)
    except WebSocketDisconnect:
        pass
    finally:
        broker.disconnect_producer(str(door_id), websocket)
        logger.info("Camera producer disconnected for door %s", door_id)


@router.websocket("/ws/camera/{door_id}/preview")
async def camera_preview_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to watch.")],
    websocket: WebSocket,
    session: SessionDep,
) -> None:
    """瀏覽器 viewer：接收特定門的相機 binary JPEG 影格。"""
    ticket = websocket.query_params.get("ticket")
    if ticket is None:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    try:
        door = await get_door_by_id(door_id, session)
    except DoorNotFoundError:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    if not door.is_active:
        await websocket.accept()
        await websocket.close(code=1008)
        return
    ticket_store = cast(WebSocketTicketStore, websocket.app.state.ws_ticket_store)
    if not ticket_store.consume(ticket, purpose="camera-preview", door_id=str(door_id)):
        await websocket.accept()
        await websocket.close(code=1008)
        return

    broker = cast(CameraFrameBroker, websocket.app.state.camera_frame_broker)
    await websocket.accept()
    await broker.connect_viewer(str(door_id), websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        await broker.disconnect_viewer(str(door_id), websocket)
        logger.info("Camera viewer disconnected for door %s", door_id)
