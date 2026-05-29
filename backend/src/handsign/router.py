import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status

from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.devices.auth import DeviceAuthError, get_device_door
from src.handsign.registry import HandsignFSMRegistry
from src.handsign.schemas import (
    HandsignFeedRequest,
    HandsignFeedResponse,
    JutsuCreateRequest,
    JutsuListResponse,
    JutsuResponse,
    JutsuUpdateRequest,
)
from src.handsign.service import (
    assign_jutsu_to_door,
    create_jutsu,
    delete_jutsu,
    get_jutsu_by_id,
    list_jutsu,
    unassign_jutsu_from_door,
    update_jutsu,
)
from src.handsign.session import DoorSessionStore
from src.users.models import User

logger = logging.getLogger(__name__)

_registry: "HandsignFSMRegistry | None" = None
_session_store: "DoorSessionStore | None" = None


def get_registry() -> "HandsignFSMRegistry":
    assert _registry is not None, "HandsignFSMRegistry not initialized"
    return _registry


def get_session_store() -> "DoorSessionStore":
    assert _session_store is not None, "DoorSessionStore not initialized"
    return _session_store


def init_handsign(
    registry: "HandsignFSMRegistry", session_store: "DoorSessionStore"
) -> None:
    global _registry, _session_store
    _registry = registry
    _session_store = session_store


router = APIRouter(tags=["jutsu"])


def _to_response(jutsu: object) -> JutsuResponse:
    return JutsuResponse.model_validate(jutsu)


@router.get("/api/jutsu", response_model=JutsuListResponse)
async def list_jutsu_endpoint(
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:read"))],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> JutsuListResponse:
    total, rows = await list_jutsu(session, skip=skip, limit=limit)
    return JutsuListResponse(
        total=total, skip=skip, limit=limit, jutsu=[_to_response(j) for j in rows]
    )


@router.get("/api/jutsu/{jutsu_id}", response_model=JutsuResponse)
async def get_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:read"))],
) -> JutsuResponse:
    return _to_response(await get_jutsu_by_id(jutsu_id, session))


@router.post(
    "/api/jutsu", response_model=JutsuResponse, status_code=status.HTTP_201_CREATED
)
async def create_jutsu_endpoint(
    request: JutsuCreateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:create"))],
) -> JutsuResponse:
    return _to_response(await create_jutsu(request, session))


@router.put("/api/jutsu/{jutsu_id}", response_model=JutsuResponse)
async def update_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    request: JutsuUpdateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:update"))],
) -> JutsuResponse:
    return _to_response(await update_jutsu(jutsu_id, request, session))


@router.delete("/api/jutsu/{jutsu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:delete"))],
) -> None:
    await delete_jutsu(jutsu_id, session)


door_jutsu_router = APIRouter(prefix="/api/doors", tags=["jutsu"])


@door_jutsu_router.post(
    "/{door_id}/jutsu/{jutsu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Assign jutsu to door",
)
async def assign_jutsu_endpoint(
    door_id: Annotated[UUID, Path()],
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("door:update"))],
) -> None:
    await assign_jutsu_to_door(door_id, jutsu_id, session)


@door_jutsu_router.delete(
    "/{door_id}/jutsu/{jutsu_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Unassign jutsu from door",
)
async def unassign_jutsu_endpoint(
    door_id: Annotated[UUID, Path()],
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("door:update"))],
) -> None:
    await unassign_jutsu_from_door(door_id, jutsu_id, session)


handsign_feed_router = APIRouter(prefix="/api/doors", tags=["handsign"])


@handsign_feed_router.post(
    "/{door_id}/handsign/feed",
    response_model=HandsignFeedResponse,
    summary="Feed a confirmed hand sign to the door FSM",
)
async def handsign_feed_endpoint(
    door_id: Annotated[UUID, Path()],
    body: HandsignFeedRequest,
    request: Request,
    session: SessionDep,
) -> HandsignFeedResponse:
    try:
        door = await get_device_door(request, door_id, session)
    except DeviceAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=exc.detail,
        ) from exc

    if door.auth_mode not in ("handsign", "both"):
        raise HTTPException(
            status_code=409, detail="Door auth_mode does not require hand signs"
        )

    registry = get_registry()
    door_state = registry.get(door_id)
    if door_state is None:
        raise HTTPException(status_code=503, detail="FSM not loaded for this door")

    completed_name: str | None = None

    async with door_state.lock:

        def _on_jutsu_complete(name: str) -> None:
            nonlocal completed_name
            completed_name = name

        door_state.fsm.on_jutsu = _on_jutsu_complete
        door_state.fsm.feed(body.sign, body.timestamp)
        progress = door_state.fsm.leading_jutsu()

    step = progress[1] if progress else 0
    total = progress[2] if progress else 0
    completed = completed_name is not None

    if completed:
        from src.doors.mqtt import publish_door_unlock

        if door.auth_mode == "handsign":
            try:
                await publish_door_unlock(door)
            except Exception as exc:
                logger.warning("MQTT publish failed for door %s: %s", door.id, exc)
        elif door.auth_mode == "both":
            store = get_session_store()
            door_session = store.get_or_create(door_id)
            door_session.handsign_ok = True
            if door_session.is_complete():
                try:
                    await publish_door_unlock(door)
                    store.clear(door_id)
                except Exception as exc:
                    logger.warning(
                        "MQTT publish failed (both mode) door %s: %s", door.id, exc
                    )

    return HandsignFeedResponse(step=step, total=total, completed=completed)
