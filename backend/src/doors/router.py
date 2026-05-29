import logging
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
    status,
)

from src.access_logs.schemas import AccessLogCreate, AccessLogResponse
from src.access_logs.service import create_access_log
from src.auth.dependencies import get_current_user, require_permission
from src.core.config import get_settings
from src.core.database import SessionDep
from src.core.exceptions import (
    DoorInactiveError,
    DoorMqttNotConfiguredError,
    PermissionDeniedError,
)
from src.core.permissions import user_permissions
from src.devices.auth import DeviceAuthError, get_device_door
from src.doors.access import (
    DOOR_DELETE_ACTION,
    DOOR_READ_ACTION,
    DOOR_UPDATE_ACTION,
    user_can_manage_door,
    user_can_unlock_door,
)
from src.doors.mqtt import DoorUnlockPublishError, publish_door_unlock
from src.doors.schemas import (
    DoorCreateRequest,
    DoorListResponse,
    DoorRecognizeResponse,
    DoorResponse,
    DoorUnlockResponse,
    DoorUpdateRequest,
)
from src.doors.service import (
    create_door,
    delete_door,
    get_door_by_id,
    list_doors,
    update_door,
)
from src.faces.engine import EngineDep
from src.faces.service import recognize_image_bytes
from src.handsign.router import get_session_store
from src.handsign.session import try_unlock_both
from src.users.models import User


router = APIRouter(prefix="/api/doors", tags=["doors"])
logger = logging.getLogger(__name__)


def _require_door_permission(rbac_permission: str, door_action: str):
    """Dependency: allow if user has the global RBAC permission OR a per-door ACL entry."""

    async def _dep(
        door_id: Annotated[UUID, Path()],
        current_user: Annotated[User, Depends(get_current_user)],
        session: SessionDep,
    ) -> User:
        perms = await user_permissions(current_user, session)
        if rbac_permission in perms:
            return current_user
        if await user_can_manage_door(current_user.id, door_id, door_action, session):
            return current_user
        raise PermissionDeniedError()

    return _dep


def _to_response(door) -> DoorResponse:
    return DoorResponse(
        id=door.id,
        name=door.name,
        mqtt_id=door.mqtt_id,
        location=door.location,
        is_active=door.is_active,
        auth_mode=door.auth_mode,
        created_at=door.created_at,
    )


@router.get(
    "",
    response_model=DoorListResponse,
    summary="List doors",
    description="Return a paginated list of all doors.",
)
async def list_doors_endpoint(
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("door:read"))],
    skip: Annotated[int, Query(ge=0, description="Doors to skip.")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum doors to return.")
    ] = 10,
) -> DoorListResponse:
    total, doors = await list_doors(session, skip=skip, limit=limit)
    return DoorListResponse(
        total=total, skip=skip, limit=limit, doors=[_to_response(d) for d in doors]
    )


@router.get(
    "/{door_id}",
    response_model=DoorResponse,
    summary="Get door",
    description="Return a single door by ID.",
)
async def get_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to fetch.")],
    session: SessionDep,
    current_user: Annotated[
        User, Depends(_require_door_permission("door:read", DOOR_READ_ACTION))
    ],
) -> DoorResponse:
    door = await get_door_by_id(door_id, session)
    return _to_response(door)


@router.post(
    "",
    response_model=DoorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create door",
    description="Create a new door. Restricted to administrators.",
)
async def create_door_endpoint(
    request: DoorCreateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("door:create"))],
) -> DoorResponse:
    door = await create_door(request, session)
    return _to_response(door)


@router.put(
    "/{door_id}",
    response_model=DoorResponse,
    summary="Update door",
    description="Update door fields. Restricted to administrators.",
)
async def update_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to update.")],
    request: DoorUpdateRequest,
    session: SessionDep,
    current_user: Annotated[
        User, Depends(_require_door_permission("door:update", DOOR_UPDATE_ACTION))
    ],
) -> DoorResponse:
    door = await update_door(door_id, request, session)
    from src.handsign.router import _reload_door_registry, _registry

    if _registry is not None:
        await _reload_door_registry(door_id, session)
    return _to_response(door)


@router.delete(
    "/{door_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete door",
    description="Delete a door. Restricted to administrators.",
)
async def delete_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to delete.")],
    session: SessionDep,
    current_user: Annotated[
        User, Depends(_require_door_permission("door:delete", DOOR_DELETE_ACTION))
    ],
) -> None:
    await delete_door(door_id, session)


@router.post(
    "/{door_id}/unlock",
    response_model=DoorUnlockResponse,
    summary="Unlock door",
    description="Send an MQTT unlock command and record the access event.",
)
async def unlock_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to unlock.")],
    request: Request,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("door:unlock"))],
) -> DoorUnlockResponse:
    door = await get_door_by_id(door_id, session)
    if not door.is_active:
        raise DoorInactiveError()

    try:
        await publish_door_unlock(door)
    except (DoorUnlockPublishError, DoorMqttNotConfiguredError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to publish door unlock command",
        ) from exc

    response = DoorUnlockResponse(
        door_id=door.id,
        user_id=current_user.id,
        username=current_user.username,
        confidence=None,
        door_opened=True,
        access_log_id=None,
    )
    try:
        access_log = await create_access_log(
            AccessLogCreate(
                door_id=door.id,
                user_id=current_user.id,
                username=current_user.username,
                confidence=None,
                door_opened=True,
            ),
            session,
        )
    except Exception:
        await session.rollback()
        logger.exception("Failed to write access log for manual door unlock")
        return response

    response.access_log_id = access_log.id
    await request.app.state.access_event_broker.publish(
        AccessLogResponse.model_validate(access_log)
    )
    return response


@router.post(
    "/{door_id}/recognize",
    response_model=DoorRecognizeResponse,
    summary="Recognize door access",
    description="Recognize a face for this door and open it when a match is found.",
)
async def recognize_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID for this recognition attempt.")],
    image: UploadFile,
    request: Request,
    session: SessionDep,
    engine: EngineDep,
) -> DoorRecognizeResponse:
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

    recognition = await recognize_image_bytes(
        await image.read(),
        session,
        engine,
        get_settings().COSINE_THRESHOLD,
    )
    if not recognition.matched:
        return DoorRecognizeResponse(
            matched=False,
            user_id=None,
            username=None,
            confidence=recognition.confidence,
            door_opened=False,
            access_log_id=None,
        )
    assert recognition.user_id is not None

    door_opened = False
    if await user_can_unlock_door(recognition.user_id, door.id, session):
        if door.auth_mode == "face":
            try:
                await publish_door_unlock(door)
                door_opened = True
            except (DoorUnlockPublishError, DoorMqttNotConfiguredError) as exc:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to publish door unlock command",
                ) from exc
        elif door.auth_mode == "both":
            try:
                session_store = get_session_store()
            except AssertionError:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Handsign service not available",
                )
            door_opened = await try_unlock_both(
                door.id,
                "face_ok",
                session_store,
                lambda: publish_door_unlock(door),
                logger,
            )
        elif door.auth_mode == "handsign":
            pass  # face recognition alone does not unlock
        else:
            logger.warning(
                "Door %s has unknown auth_mode %r, skipping unlock",
                door.id,
                door.auth_mode,
            )

    response = DoorRecognizeResponse(
        matched=True,
        user_id=recognition.user_id,
        username=recognition.username,
        confidence=recognition.confidence,
        door_opened=door_opened,
        access_log_id=None,
    )
    try:
        access_log = await create_access_log(
            AccessLogCreate(
                door_id=door.id,
                user_id=recognition.user_id,
                username=recognition.username,
                confidence=recognition.confidence,
                door_opened=door_opened,
            ),
            session,
        )
    except Exception as exc:
        await session.rollback()
        logger.exception("Failed to write access log for door recognition")
        if door_opened:
            return response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record door recognition event",
        ) from exc

    response.access_log_id = access_log.id
    await request.app.state.access_event_broker.publish(
        AccessLogResponse.model_validate(access_log)
    )
    return response
