from uuid import UUID

from sqlalchemy import delete
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import DoorNotFoundError
from src.doors.models import Door, UserDoorPermission
from src.users.models import User


DOOR_UNLOCK_ACTION = "unlock"
DOOR_READ_ACTION = "read"
DOOR_UPDATE_ACTION = "update"
DOOR_DELETE_ACTION = "delete"


async def _active_user_has_door_permission(
    user_id: UUID,
    door_id: UUID,
    action: str,
    session: AsyncSession,
) -> bool:
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        return False
    access = await session.get(UserDoorPermission, (user_id, door_id, action))
    return access is not None


async def user_can_unlock_door(
    user_id: UUID,
    door_id: UUID,
    session: AsyncSession,
) -> bool:
    return await _active_user_has_door_permission(
        user_id, door_id, DOOR_UNLOCK_ACTION, session
    )


async def user_can_manage_door(
    user_id: UUID,
    door_id: UUID,
    action: str,
    session: AsyncSession,
) -> bool:
    return await _active_user_has_door_permission(user_id, door_id, action, session)


async def delete_permissions_for_user(
    user_id: UUID,
    session: AsyncSession,
) -> None:
    await session.exec(
        delete(UserDoorPermission).where(
            UserDoorPermission.user_id == user_id  # type: ignore[arg-type]
        )
    )


async def delete_permissions_for_door(
    door_id: UUID,
    session: AsyncSession,
) -> None:
    await session.exec(
        delete(UserDoorPermission).where(
            UserDoorPermission.door_id == door_id  # type: ignore[arg-type]
        )
    )


async def list_user_door_access(
    user_id: UUID,
    session: AsyncSession,
    *,
    action: str = DOOR_UNLOCK_ACTION,
) -> list[UUID]:
    return list(
        (
            await session.exec(
                select(UserDoorPermission.door_id).where(
                    UserDoorPermission.user_id == user_id,
                    UserDoorPermission.action == action,
                )
            )
        ).all()
    )


async def replace_user_door_access(
    user_id: UUID,
    door_ids: list[UUID],
    session: AsyncSession,
    *,
    action: str = DOOR_UNLOCK_ACTION,
) -> list[UUID]:
    unique_door_ids = list(dict.fromkeys(door_ids))
    if unique_door_ids:
        found = set(
            (
                await session.exec(select(Door.id).where(Door.id.in_(unique_door_ids)))  # type: ignore[attr-defined]
            ).all()
        )
        if found != set(unique_door_ids):
            raise DoorNotFoundError()

    await session.exec(
        delete(UserDoorPermission).where(
            UserDoorPermission.user_id == user_id,  # type: ignore[arg-type]
            UserDoorPermission.action == action,  # type: ignore[arg-type]
        )
    )
    session.add_all(
        UserDoorPermission(
            user_id=user_id,
            door_id=door_id,
            action=action,
        )
        for door_id in unique_door_ids
    )
    await session.commit()
    return unique_door_ids
