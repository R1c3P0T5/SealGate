from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.doors.schemas import (
    DoorCreateRequest,
    DoorListResponse,
    DoorResponse,
    DoorUpdateRequest,
)
from src.doors.service import (
    create_door,
    delete_door,
    get_door_by_id,
    list_doors,
    update_door,
)
from src.users.models import User


router = APIRouter(prefix="/api/doors", tags=["doors"])


def _to_response(door) -> DoorResponse:
    return DoorResponse(
        id=door.id,
        name=door.name,
        mqtt_id=door.mqtt_id,
        location=door.location,
        is_active=door.is_active,
        created_at=door.created_at,
    )


@router.get(
    "",
    response_model=DoorListResponse,
    summary="List doors",
    description="Return a paginated list of all doors. No authentication required.",
)
async def list_doors_endpoint(
    session: SessionDep,
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
    description="Return a single door by ID. No authentication required.",
)
async def get_door_endpoint(
    door_id: Annotated[UUID, Path(description="Door ID to fetch.")],
    session: SessionDep,
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
    current_user: Annotated[User, Depends(require_permission("door:update"))],
) -> DoorResponse:
    door = await update_door(door_id, request, session)
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
    current_user: Annotated[User, Depends(require_permission("door:delete"))],
) -> None:
    await delete_door(door_id, session)
