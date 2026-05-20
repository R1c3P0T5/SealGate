from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.core.exceptions import DoorInactiveError
from src.doors.service import get_door_by_id
from src.users.models import User
from src.ws_tickets.store import WebSocketTicketStore

router = APIRouter(prefix="/api/ws-tickets", tags=["ws-tickets"])


class CameraPreviewTicketRequest(BaseModel):
    door_id: UUID = Field(description="Door ID to preview.")


class WebSocketTicketResponse(BaseModel):
    ticket: str = Field(description="Short-lived one-time WebSocket ticket.")
    expires_at: datetime = Field(description="UTC timestamp when the ticket expires.")


@router.post(
    "/camera-preview",
    response_model=WebSocketTicketResponse,
    summary="Create camera preview WebSocket ticket",
    description="Create a short-lived one-time ticket for a door camera preview WebSocket.",
)
async def create_camera_preview_ticket(
    payload: CameraPreviewTicketRequest,
    request: Request,
    session: SessionDep,
    _current_user: Annotated[User, Depends(require_permission("camera:preview"))],
) -> WebSocketTicketResponse:
    door = await get_door_by_id(payload.door_id, session)
    if not door.is_active:
        raise DoorInactiveError()

    store = cast(WebSocketTicketStore, request.app.state.ws_ticket_store)
    ticket = store.issue(
        purpose="camera-preview",
        door_id=str(door.id),
        ttl_seconds=30,
    )
    return WebSocketTicketResponse(
        ticket=ticket.ticket,
        expires_at=ticket.expires_at,
    )
