from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from src.auth.dependencies import get_current_user, require_permission
from src.auth.schemas import UserResponse
from src.core.database import SessionDep
from src.core.permissions import check_access
from src.doors.access import list_user_door_access, replace_user_door_access
from src.handsign.access import list_user_jutsu_access, replace_user_jutsu_access
from src.permissions.schemas import (
    SetUserPermissionsRequest,
    SetUserRoleRequest,
    UserPermissionsResponse,
)
from src.permissions.service import (
    permissions_detail,
    set_overrides,
    set_user_role,
)
from src.roles.models import Role
from src.users.models import User
from src.users.schemas import (
    ChangePasswordRequest,
    SetUserActiveRequest,
    SetUserDoorAccessRequest,
    SetUserJutsuAccessRequest,
    UserDoorAccessResponse,
    UserJutsuAccessResponse,
    UserListResponse,
    UserResponseFull,
    UserUpdateRequest,
)
from src.users.service import (
    change_password,
    delete_user,
    get_user_by_id,
    list_users,
    set_user_active,
    update_user,
    user_response,
)


DoorAction = Literal["unlock", "read", "update", "delete"]
JutsuAction = Literal["read", "update", "delete"]

router = APIRouter(prefix="/api/users", tags=["users"])


async def _role_name(user: User, session: SessionDep) -> str:
    role = await session.get(Role, user.role_id)
    if role is None:
        raise RuntimeError("User role seed data is missing.")
    return role.name


async def _full_user_response(user: User, session: SessionDep) -> UserResponseFull:
    return UserResponseFull(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role_name=await _role_name(user, session),
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get(
    "",
    response_model=UserListResponse,
    summary="List users",
    description=(
        "Return a paginated list of users. This operation is restricted to "
        "administrators because it exposes account metadata for multiple users."
    ),
    response_description="Paginated users with total count and face embedding sizes.",
)
async def list_users_endpoint(
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:read"))],
    skip: Annotated[
        int,
        Query(
            ge=0,
            description="Number of users to skip before returning results.",
        ),
    ] = 0,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Maximum number of users to return.",
        ),
    ] = 10,
) -> UserListResponse:
    total, users = await list_users(session, skip=skip, limit=limit)
    return UserListResponse(
        total=total,
        skip=skip,
        limit=limit,
        users=[await _full_user_response(user, session) for user in users],
    )


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user profile",
    description=(
        "Return a user's public profile by ID. A valid bearer token is required."
    ),
    response_description="The requested user's public profile.",
)
async def get_user(
    user_id: Annotated[UUID, Path(description="User ID to fetch.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    await check_access(current_user, user_id, "user:read", session)
    user = await get_user_by_id(user_id, session)
    return await user_response(user, session)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user profile",
    description=(
        "Update profile fields for the requested user. Users may update their "
        "own profile; administrators may update any user's profile."
    ),
    response_description="The updated user profile.",
)
async def update_user_profile(
    user_id: Annotated[UUID, Path(description="User ID to update.")],
    request: UserUpdateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    await check_access(current_user, user_id, "user:update", session)
    user = await update_user(user_id, request, session)
    return await user_response(user, session)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description=(
        "Delete the requested user account. Users may delete their own account; "
        "administrators may delete any user account."
    ),
    response_description="No content.",
)
async def delete_user_profile(
    user_id: Annotated[UUID, Path(description="User ID to delete.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await check_access(current_user, user_id, "user:delete", session)
    await delete_user(user_id, session)


@router.put(
    "/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password",
    description=(
        "Change a user's password. Users must supply their current password when "
        "changing their own. Administrators may change any user's password without "
        "providing the current password."
    ),
)
async def change_user_password(
    user_id: Annotated[UUID, Path(description="User ID whose password to change.")],
    request: ChangePasswordRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await check_access(current_user, user_id, "user:update", session)
    await change_password(user_id, request, current_user, session)


@router.get("/{user_id}/permissions", response_model=UserPermissionsResponse)
async def user_permissions(
    user_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserPermissionsResponse:
    await check_access(current_user, user_id, "user:read", session)
    user = await get_user_by_id(user_id, session)
    detail = await permissions_detail(user, session)
    return UserPermissionsResponse(**detail)


@router.put("/{user_id}/permissions", response_model=UserPermissionsResponse)
async def set_permissions(
    user_id: Annotated[UUID, Path()],
    request: SetUserPermissionsRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
) -> UserPermissionsResponse:
    user = await get_user_by_id(user_id, session)
    overrides = [o.model_dump() for o in request.overrides]
    await set_overrides(user, overrides, session)
    detail = await permissions_detail(user, session)
    return UserPermissionsResponse(**detail)


@router.get("/{user_id}/doors", response_model=UserDoorAccessResponse)
async def user_door_access(
    user_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
    action: Annotated[
        DoorAction, Query(description="Door permission action to query.")
    ] = "unlock",
) -> UserDoorAccessResponse:
    await get_user_by_id(user_id, session)
    door_ids = await list_user_door_access(user_id, session, action=action)
    return UserDoorAccessResponse(door_ids=door_ids)


@router.put("/{user_id}/doors", response_model=UserDoorAccessResponse)
async def set_user_door_access(
    user_id: Annotated[UUID, Path()],
    request: SetUserDoorAccessRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
    action: Annotated[
        DoorAction, Query(description="Door permission action to assign.")
    ] = "unlock",
) -> UserDoorAccessResponse:
    await get_user_by_id(user_id, session)
    door_ids = await replace_user_door_access(
        user_id, request.door_ids, session, action=action
    )
    return UserDoorAccessResponse(door_ids=door_ids)


@router.get("/{user_id}/jutsu", response_model=UserJutsuAccessResponse)
async def user_jutsu_access(
    user_id: Annotated[UUID, Path()],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
    action: Annotated[
        JutsuAction, Query(description="Jutsu permission action to query.")
    ] = "read",
) -> UserJutsuAccessResponse:
    await get_user_by_id(user_id, session)
    jutsu_ids = await list_user_jutsu_access(user_id, session, action=action)
    return UserJutsuAccessResponse(jutsu_ids=jutsu_ids)


@router.put("/{user_id}/jutsu", response_model=UserJutsuAccessResponse)
async def set_user_jutsu_access(
    user_id: Annotated[UUID, Path()],
    request: SetUserJutsuAccessRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
    action: Annotated[
        JutsuAction, Query(description="Jutsu permission action to assign.")
    ] = "read",
) -> UserJutsuAccessResponse:
    await get_user_by_id(user_id, session)
    jutsu_ids = await replace_user_jutsu_access(
        user_id, request.jutsu_ids, session, action=action
    )
    return UserJutsuAccessResponse(jutsu_ids=jutsu_ids)


@router.put("/{user_id}/role", response_model=UserResponse)
async def set_role(
    user_id: Annotated[UUID, Path()],
    request: SetUserRoleRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
) -> UserResponse:
    user = await get_user_by_id(user_id, session)
    updated_user, _ = await set_user_role(user, request.role_id, session)
    return await user_response(updated_user, session)


@router.put(
    "/{user_id}/active",
    response_model=UserResponse,
    summary="Set user active flag",
    description=(
        "Activate or deactivate a user account. Administrators only. "
        "Deactivated users cannot authenticate until reactivated."
    ),
    response_description="The updated user profile.",
)
async def set_active(
    user_id: Annotated[UUID, Path(description="User ID to update.")],
    request: SetUserActiveRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("user:manage"))],
) -> UserResponse:
    user = await set_user_active(user_id, request.is_active, session)
    return await user_response(user, session)
