from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.handsign.schemas import (
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
from src.users.models import User

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
