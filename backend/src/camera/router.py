import json
import logging
import math
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
    get_device_door,
)
from src.doors.service import get_door_by_id
from src.ws_tickets.store import WebSocketTicketStore

router = APIRouter(tags=["camera"])
logger = logging.getLogger(__name__)


def _metadata_number(value: object) -> float | None:
    if not isinstance(value, int | float) or isinstance(value, bool):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


def _hand_box_payload(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    x = _metadata_number(value.get("x"))
    y = _metadata_number(value.get("y"))
    width = _metadata_number(value.get("width"))
    height = _metadata_number(value.get("height"))
    if x is None or y is None or width is None or height is None:
        return None
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None
    if x > 1.0001 or y > 1.0001 or x + width > 1.0001 or y + height > 1.0001:
        return None
    box: dict[str, object] = {"x": x, "y": y, "width": width, "height": height}
    score = _metadata_number(value.get("score"))
    if score is not None:
        box["score"] = score
    sign = value.get("sign")
    if isinstance(sign, str) and sign:
        box["sign"] = sign
    return box


def _hand_meta_box_payload(value: object) -> dict[str, object] | None:
    """Parse Jetson hand_meta entry: {box: [x,y,w,h], sign, confidence}."""
    if not isinstance(value, dict):
        return None
    raw_box = value.get("box")
    if not isinstance(raw_box, list) or len(raw_box) != 4:
        return None
    x = _metadata_number(raw_box[0])
    y = _metadata_number(raw_box[1])
    width = _metadata_number(raw_box[2])
    height = _metadata_number(raw_box[3])
    if x is None or y is None or width is None or height is None:
        return None
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None
    if x > 1.0001 or y > 1.0001 or x + width > 1.0001 or y + height > 1.0001:
        return None
    box: dict[str, object] = {"x": x, "y": y, "width": width, "height": height}
    score = _metadata_number(value.get("confidence"))
    if score is not None:
        box["score"] = score
    sign = value.get("sign")
    if isinstance(sign, str) and sign:
        box["sign"] = sign
    return box


def _face_box_payload(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    x = _metadata_number(value.get("x"))
    y = _metadata_number(value.get("y"))
    width = _metadata_number(value.get("width"))
    height = _metadata_number(value.get("height"))
    if x is None or y is None or width is None or height is None:
        return None
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        return None
    if (
        x > 1.0001  # 1.0001 absorbs float rounding from worker's round(..., 6)
        or y > 1.0001
        or x + width > 1.0001
        or y + height > 1.0001
    ):
        return None

    face_box = {"x": x, "y": y, "width": width, "height": height}
    score = _metadata_number(value.get("score"))
    if score is not None:
        face_box["score"] = score
    return face_box


def _camera_metadata_payload(text: str) -> dict[str, object] | None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    msg_type = payload.get("type")

    if msg_type == "face_boxes":
        raw_faces = payload.get("faces")
        if not isinstance(raw_faces, list):
            return None
        faces: list[dict[str, float]] = []
        for raw_face in raw_faces:
            face = _face_box_payload(raw_face)
            if face is None:
                continue
            faces.append(face)
        return {"type": "face_boxes", "faces": faces}

    if msg_type == "hand_boxes":
        raw_hands = payload.get("hands")
        if not isinstance(raw_hands, list):
            return None
        hands: list[dict[str, object]] = []
        for raw_hand in raw_hands:
            hand = _hand_box_payload(raw_hand)
            if hand is None:
                continue
            hands.append(hand)
        return {"type": "hand_boxes", "hands": hands}

    if msg_type == "hand_meta":
        # Jetson sends {box: [x,y,w,h], sign, confidence}; normalise to hand_boxes.
        raw_hands = payload.get("hands")
        if not isinstance(raw_hands, list):
            return None
        hands_meta: list[dict[str, object]] = []
        for raw_hand in raw_hands:
            hand = _hand_meta_box_payload(raw_hand)
            if hand is None:
                continue
            hands_meta.append(hand)
        return {"type": "hand_boxes", "hands": hands_meta}

    return None


@router.websocket("/ws/camera/{door_id}/push")
async def camera_push_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID this producer serves.")],
    websocket: WebSocket,
    session: SessionDep,
) -> None:
    """Jetson producer：送出 binary JPEG 影格，接收 start/stop 控制。"""
    try:
        await get_device_door(websocket, door_id, session)
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
            text = message.get("text")
            if text is not None:
                payload = _camera_metadata_payload(text)
                if payload is not None:
                    await broker.relay_metadata(str(door_id), payload, websocket)
                continue
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
