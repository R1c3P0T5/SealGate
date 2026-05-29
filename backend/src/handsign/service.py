from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import (
    JutsuAlreadyAssignedError,
    JutsuNameAlreadyExistsError,
    JutsuNotAssignedError,
    JutsuNotFoundError,
)
from src.doors.service import get_door_by_id
from src.handsign.models import DoorJutsu, Jutsu
from src.handsign.schemas import JutsuCreateRequest, JutsuUpdateRequest


async def get_jutsu_by_id(jutsu_id: UUID, session: AsyncSession) -> Jutsu:
    jutsu = await session.get(Jutsu, jutsu_id)
    if jutsu is None:
        raise JutsuNotFoundError()
    return jutsu


async def list_jutsu(
    session: AsyncSession, skip: int = 0, limit: int = 10
) -> tuple[int, list[Jutsu]]:
    total = (await session.exec(select(func.count()).select_from(Jutsu))).one()
    rows = list((await session.exec(select(Jutsu).offset(skip).limit(limit))).all())
    return total, rows


async def create_jutsu(request: JutsuCreateRequest, session: AsyncSession) -> Jutsu:
    jutsu = Jutsu(name=request.name, signs=request.signs)
    session.add(jutsu)
    try:
        await session.commit()
        await session.refresh(jutsu)
    except IntegrityError as exc:
        await session.rollback()
        raise JutsuNameAlreadyExistsError() from exc
    return jutsu


async def update_jutsu(
    jutsu_id: UUID, request: JutsuUpdateRequest, session: AsyncSession
) -> Jutsu:
    jutsu = await get_jutsu_by_id(jutsu_id, session)
    if request.name is not None:
        jutsu.name = request.name
    if request.signs is not None:
        jutsu.signs = request.signs
    session.add(jutsu)
    try:
        await session.commit()
        await session.refresh(jutsu)
    except IntegrityError as exc:
        await session.rollback()
        raise JutsuNameAlreadyExistsError() from exc
    return jutsu


async def delete_jutsu(jutsu_id: UUID, session: AsyncSession) -> None:
    jutsu = await get_jutsu_by_id(jutsu_id, session)
    await session.delete(jutsu)
    await session.commit()


async def assign_jutsu_to_door(
    door_id: UUID, jutsu_id: UUID, session: AsyncSession
) -> None:
    await get_door_by_id(door_id, session)
    await get_jutsu_by_id(jutsu_id, session)
    existing = await session.get(DoorJutsu, (door_id, jutsu_id))
    if existing is not None:
        raise JutsuAlreadyAssignedError()
    session.add(DoorJutsu(door_id=door_id, jutsu_id=jutsu_id))
    await session.commit()


async def unassign_jutsu_from_door(
    door_id: UUID, jutsu_id: UUID, session: AsyncSession
) -> None:
    link = await session.get(DoorJutsu, (door_id, jutsu_id))
    if link is None:
        raise JutsuNotAssignedError()
    await session.delete(link)
    await session.commit()


async def get_door_jutsu(door_id: UUID, session: AsyncSession) -> list[Jutsu]:
    stmt = (
        select(Jutsu)
        .join(DoorJutsu, col(DoorJutsu.jutsu_id) == col(Jutsu.id))
        .where(DoorJutsu.door_id == door_id)
    )
    return list((await session.exec(stmt)).all())
