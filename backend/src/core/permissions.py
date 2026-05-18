from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import PermissionDeniedError
from src.permissions.models import Permission, RolePermission, UserPermissionOverride
from src.users.models import User


async def get_user_permissions(user: User, session: AsyncSession) -> set[str]:
    """Return effective permission set for a user (role defaults + per-user overrides)."""
    role_stmt = select(Permission.name).where(
        Permission.id.in_(  # type: ignore[attr-defined]
            select(RolePermission.permission_id).where(
                RolePermission.role_id == user.role_id
            )
        )
    )
    result = set((await session.exec(role_stmt)).all())

    override_stmt = select(Permission.name, UserPermissionOverride.granted).where(
        UserPermissionOverride.user_id == user.id,
        UserPermissionOverride.permission_id == Permission.id,  # type: ignore[arg-type]
    )
    for name, granted in (await session.exec(override_stmt)).all():
        if granted:
            result.add(name)
        else:
            result.discard(name)

    return result


async def require_self_or_permission(
    current_user: User, user_id: UUID, permission: str, session: AsyncSession
) -> None:
    """Allow if current_user is the target user, else require named permission."""
    if current_user.id == user_id:
        return
    perms = await get_user_permissions(current_user, session)
    if permission not in perms:
        raise PermissionDeniedError()
