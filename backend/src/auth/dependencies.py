from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from src.auth.utils import decode_token
from src.core.database import SessionDep
from src.core.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
)
from src.roles.models import Role
from src.users.models import User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: SessionDep,
) -> User:
    """Verify JWT access token and return the active current user."""

    payload = decode_token(token)
    if payload is None:
        raise InvalidTokenError()

    user_id = payload.get("sub")
    if not isinstance(user_id, str):
        raise InvalidTokenError()

    try:
        user_uuid = UUID(user_id)
    except ValueError as exc:
        raise InvalidTokenError() from exc

    user = await session.get(User, user_uuid)

    if user is None:
        raise InvalidTokenError()

    if not user.is_active:
        raise InactiveUserError()

    return user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
    session: SessionDep,
) -> User:
    """Verify current user has the admin role."""

    role = await session.get(Role, current_user.role_id)
    if role is None or role.name != "admin":
        raise PermissionDeniedError()

    return current_user


def require_permission(permission: str) -> Callable[..., object]:
    """Create a dependency that requires the named effective permission."""

    async def dependency(
        current_user: Annotated[User, Depends(get_current_user)],
        session: SessionDep,
    ) -> User:
        from src.core.permissions import user_permissions

        permissions = await user_permissions(current_user, session)
        if permission not in permissions:
            raise PermissionDeniedError()
        return current_user

    return dependency
