from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query

from src.auth.dependencies import get_admin_user, get_current_user
from src.core.database import SessionDep
from src.roles.schemas import (
    PermissionSummary,
    RoleListResponse,
    RolePermissionsResponse,
    RoleResponse,
    RoleUsersResponse,
)
from src.roles.service import (
    list_roles as _list_roles,
    role_by_id,
    role_permissions as _role_permissions,
    role_users as _role_users,
)
from src.users.models import User

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("", response_model=RoleListResponse)
async def list_roles(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> RoleListResponse:
    total, roles = await _list_roles(session, skip=skip, limit=limit)
    return RoleListResponse(
        total=total,
        skip=skip,
        limit=limit,
        roles=[
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description,
                created_at=r.created_at,
            )
            for r in roles
        ],
    )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> RoleResponse:
    role = await role_by_id(role_id, session)
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
    )


@router.get("/{role_id}/permissions", response_model=RolePermissionsResponse)
async def role_permissions(
    role_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> RolePermissionsResponse:
    await role_by_id(role_id, session)
    perms = await _role_permissions(role_id, session)
    return RolePermissionsResponse(
        role_id=role_id,
        permissions=[
            PermissionSummary(id=p.id, name=p.name, description=p.description)
            for p in perms
        ],
    )


@router.get("/{role_id}/users", response_model=RoleUsersResponse)
async def role_users(
    role_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_admin_user)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RoleUsersResponse:
    await role_by_id(role_id, session)
    total, users = await _role_users(role_id, session, skip=skip, limit=limit)
    return RoleUsersResponse(
        role_id=role_id,
        total=total,
        skip=skip,
        limit=limit,
        user_ids=[u.id for u in users],
    )
