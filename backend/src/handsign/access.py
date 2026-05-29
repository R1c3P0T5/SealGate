from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import JutsuNotFoundError
from src.handsign.models import Jutsu, UserJutsuPermission
from src.users.models import User


JUTSU_READ_ACTION = "read"
JUTSU_UPDATE_ACTION = "update"
JUTSU_DELETE_ACTION = "delete"


async def _active_user_has_jutsu_permission(
    user_id: UUID,
    jutsu_id: UUID,
    action: str,
    session: AsyncSession,
) -> bool:
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return False
    access = await session.get(UserJutsuPermission, (user_id, jutsu_id, action))
    return access is not None


async def user_can_manage_jutsu(
    user_id: UUID,
    jutsu_id: UUID,
    action: str,
    session: AsyncSession,
) -> bool:
    return await _active_user_has_jutsu_permission(user_id, jutsu_id, action, session)


async def list_user_jutsu_access(
    user_id: UUID,
    session: AsyncSession,
    *,
    action: str = JUTSU_READ_ACTION,
) -> list[UUID]:
    return list(
        (
            await session.exec(
                select(UserJutsuPermission.jutsu_id).where(
                    UserJutsuPermission.user_id == user_id,
                    UserJutsuPermission.action == action,
                )
            )
        ).all()
    )


async def replace_user_jutsu_access(
    user_id: UUID,
    jutsu_ids: list[UUID],
    session: AsyncSession,
    *,
    action: str = JUTSU_READ_ACTION,
) -> list[UUID]:
    unique_ids = list(dict.fromkeys(jutsu_ids))
    if unique_ids:
        found = set(
            (
                await session.exec(select(Jutsu.id).where(Jutsu.id.in_(unique_ids)))  # type: ignore[attr-defined]
            ).all()
        )
        if found != set(unique_ids):
            raise JutsuNotFoundError()

    await session.exec(
        delete(UserJutsuPermission).where(
            UserJutsuPermission.user_id == user_id,  # type: ignore[arg-type]
            UserJutsuPermission.action == action,  # type: ignore[arg-type]
        )
    )
    session.add_all(
        UserJutsuPermission(user_id=user_id, jutsu_id=jutsu_id, action=action)
        for jutsu_id in unique_ids
    )
    await session.commit()
    return unique_ids
