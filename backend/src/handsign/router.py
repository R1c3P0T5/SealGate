import logging
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlmodel.ext.asyncio.session import AsyncSession

from src.access_logs.schemas import AccessLogCreate, AccessLogResponse
from src.access_logs.service import create_access_log
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
    assign_door_jutsu,
    create_jutsu,
    delete_jutsu,
    get_door_jutsu,
    get_jutsu_by_id,
    list_jutsu,
    unassign_door_jutsu,
    update_jutsu,
)
from src.handsign.session import DoorSessionStore, try_unlock_both
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


async def _reload_door_registry(door_id: UUID, session: AsyncSession) -> None:
    from src.doors.service import get_door_by_id
    from src.handsign.jutsu import SIGN_KANJI

    if _registry is None:
        return

    try:
        door = await get_door_by_id(door_id, session)
    except Exception:
        _registry.unload(door_id)
        return

    if door.auth_mode not in ("handsign", "both"):
        _registry.unload(door_id)
        return

    try:
        jutsu_rows = await get_door_jutsu(door_id, session)
    except Exception:
        logger.warning("Failed to reload jutsu for door %s", door_id)
        return
    jutsu_dict: dict[str, list[str]] = {}
    for j in jutsu_rows:
        unknown = [s for s in j.signs if s not in SIGN_KANJI]
        if unknown:
            logger.warning(
                "Jutsu %r has unknown signs %s, skipping them", j.name, unknown
            )
        kanji_seq = [SIGN_KANJI[s] for s in j.signs if s in SIGN_KANJI]
        if kanji_seq:
            jutsu_dict[j.name] = kanji_seq
    if jutsu_dict:
        _registry.load(door_id, jutsu_dict)
    else:
        _registry.unload(door_id)


jutsu_router = APIRouter(tags=["jutsu"])


def _to_response(jutsu: object) -> JutsuResponse:
    return JutsuResponse.model_validate(jutsu)


@jutsu_router.get("/api/jutsu", response_model=JutsuListResponse)
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


@jutsu_router.get("/api/jutsu/{jutsu_id}", response_model=JutsuResponse)
async def get_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:read"))],
) -> JutsuResponse:
    return _to_response(await get_jutsu_by_id(jutsu_id, session))


@jutsu_router.post(
    "/api/jutsu", response_model=JutsuResponse, status_code=status.HTTP_201_CREATED
)
async def create_jutsu_endpoint(
    request: JutsuCreateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:create"))],
) -> JutsuResponse:
    return _to_response(await create_jutsu(request, session))


@jutsu_router.put("/api/jutsu/{jutsu_id}", response_model=JutsuResponse)
async def update_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    request: JutsuUpdateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:update"))],
) -> JutsuResponse:
    return _to_response(await update_jutsu(jutsu_id, request, session))


@jutsu_router.delete("/api/jutsu/{jutsu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_jutsu_endpoint(
    jutsu_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("jutsu:delete"))],
) -> None:
    await delete_jutsu(jutsu_id, session)


handsign_door_router = APIRouter(prefix="/api/doors", tags=["jutsu"])


@handsign_door_router.post(
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
    await assign_door_jutsu(door_id, jutsu_id, session)
    await _reload_door_registry(door_id, session)


@handsign_door_router.delete(
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
    await unassign_door_jutsu(door_id, jutsu_id, session)
    await _reload_door_registry(door_id, session)


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
    if not request.headers.get("x-device-token"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing device token",
        )
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

    try:
        registry = get_registry()
    except AssertionError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Handsign service not available",
        )
    door_state = registry.get(door_id)
    if door_state is None:
        raise HTTPException(status_code=503, detail="FSM not loaded for this door")

    completed_name: str | None = None

    async with door_state.lock:
        # Re-fetch in case registry was reloaded between get() and lock acquisition
        current = registry.get(door_id)
        if current is None:
            raise HTTPException(status_code=503, detail="FSM not loaded for this door")

        completed_name = current.fsm.feed(body.sign, body.timestamp)
        progress = current.fsm.leading_jutsu()

    step = progress[1] if progress else 0
    total = progress[2] if progress else 0
    completed = completed_name is not None

    if completed:
        from src.doors.mqtt import publish_door_unlock

        if door.auth_mode == "handsign":
            door_unlocked = False
            try:
                await publish_door_unlock(door)
                door_unlocked = True
            except Exception as exc:
                logger.warning("MQTT publish failed for door %s: %s", door.id, exc)
            if door_unlocked:
                try:
                    access_log = await create_access_log(
                        AccessLogCreate(
                            door_id=door.id,
                            user_id=None,
                            username=None,
                            confidence=None,
                            door_opened=True,
                        ),
                        session,
                    )
                    await request.app.state.access_event_broker.publish(
                        AccessLogResponse.model_validate(access_log)
                    )
                except Exception:
                    await session.rollback()
                    logger.warning(
                        "Failed to write access log for handsign unlock on door %s",
                        door.id,
                    )
        elif door.auth_mode == "both":
            try:
                store = get_session_store()
            except AssertionError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Handsign service not available",
                )
            await try_unlock_both(
                door_id,
                "handsign_ok",
                store,
                lambda: publish_door_unlock(door),
                logger,
            )
            # access log for both-mode is written by recognize_door_endpoint
            # (which has user_id); writing an anonymous log here would duplicate it

    from src.camera.broker import CameraFrameBroker

    progress_payload: dict[str, object] = {
        "type": "handsign_progress",
        "step": step,
        "total": total,
        "completed": completed,
    }
    if completed_name is not None:
        progress_payload["jutsu"] = completed_name
    camera_broker = cast(CameraFrameBroker, request.app.state.camera_frame_broker)
    await camera_broker.relay_metadata(str(door_id), progress_payload)

    return HandsignFeedResponse(step=step, total=total, completed=completed)
