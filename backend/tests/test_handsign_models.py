import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.doors.models import Door
from src.handsign.models import DoorJutsu, Jutsu


@pytest.mark.asyncio
async def test_jutsu_create_and_fetch(database_session: AsyncSession) -> None:
    jutsu = Jutsu(name="火遁・豪火球の術", signs=["i", "tora"])
    database_session.add(jutsu)
    await database_session.commit()
    await database_session.refresh(jutsu)

    fetched = await database_session.get(Jutsu, jutsu.id)
    assert fetched is not None
    assert fetched.signs == ["i", "tora"]


@pytest.mark.asyncio
async def test_door_jutsu_junction(database_session: AsyncSession) -> None:
    door = Door(name="Test Door", auth_mode="handsign")
    jutsu = Jutsu(name="水遁・水球の術", signs=["ne", "uma"])
    database_session.add(door)
    database_session.add(jutsu)
    await database_session.commit()

    link = DoorJutsu(door_id=door.id, jutsu_id=jutsu.id)
    database_session.add(link)
    await database_session.commit()

    result = (
        await database_session.exec(
            select(DoorJutsu).where(DoorJutsu.door_id == door.id)
        )
    ).all()
    assert len(result) == 1
    assert result[0].jutsu_id == jutsu.id


@pytest.mark.asyncio
async def test_door_auth_mode_default(database_session: AsyncSession) -> None:
    door = Door(name="Default Auth Door")
    database_session.add(door)
    await database_session.commit()
    await database_session.refresh(door)
    assert door.auth_mode == "face"
