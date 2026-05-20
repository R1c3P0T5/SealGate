from typing import cast
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from src.access_events.broker import AccessEventBroker
from src.auth.utils import decode_token
from src.core.database import SessionDep
from src.core.permissions import user_permissions
from src.users.models import User


router = APIRouter(tags=["access-events"])


def _websocket_token(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization")
    if authorization is not None:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token

    return websocket.query_params.get("access_token")


async def _can_read_access_events(websocket: WebSocket, session: SessionDep) -> bool:
    token = _websocket_token(websocket)
    if token is None:
        return False

    payload = decode_token(token)
    user_id = payload.get("sub") if payload is not None else None
    if not isinstance(user_id, str):
        return False

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        return False

    user = await session.get(User, user_uuid)
    if user is None or not user.is_active:
        return False

    permissions = await user_permissions(user, session)
    return "log:read" in permissions


@router.websocket("/ws/events/access")
async def access_events_websocket(
    websocket: WebSocket,
    session: SessionDep,
) -> None:
    if not await _can_read_access_events(websocket, session):
        await websocket.accept()
        await websocket.close(code=1008)
        return

    broker = cast(AccessEventBroker, websocket.app.state.access_event_broker)
    await websocket.accept()
    broker.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except WebSocketDisconnect:
        pass
    finally:
        broker.disconnect(websocket)
