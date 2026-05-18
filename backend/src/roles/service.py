from uuid import UUID

from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import BaseAPIError
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


class RoleNotFoundError(BaseAPIError):
    status_code = 404
    detail = "Role not found"


async def list_roles(
    session: AsyncSession, skip: int = 0, limit: int = 50
) -> tuple[int, list[Role]]:
    total = (await session.exec(select(func.count()).select_from(Role))).one()
    roles = (await session.exec(select(Role).offset(skip).limit(limit))).all()
    return total, list(roles)


async def get_role_by_id(role_id: UUID, session: AsyncSession) -> Role:
    role = await session.get(Role, role_id)
    if role is None:
        raise RoleNotFoundError()
    return role


async def get_role_permissions(
    role_id: UUID, session: AsyncSession
) -> list[Permission]:
    # WHERE + subquery avoids join onclause which pyright infers as bool
    stmt = select(Permission).where(
        Permission.id.in_(  # type: ignore[attr-defined]
            select(RolePermission.permission_id).where(
                RolePermission.role_id == role_id
            )
        )
    )
    return list((await session.exec(stmt)).all())


async def list_role_users(
    role_id: UUID, session: AsyncSession, skip: int = 0, limit: int = 20
) -> tuple[int, list[User]]:
    total = (
        await session.exec(
            select(func.count()).select_from(User).where(User.role_id == role_id)  # type: ignore[arg-type]
        )
    ).one()
    users = (
        await session.exec(
            select(User)
            .where(User.role_id == role_id)  # type: ignore[arg-type]
            .offset(skip)
            .limit(limit)
        )
    ).all()
    return total, list(users)
