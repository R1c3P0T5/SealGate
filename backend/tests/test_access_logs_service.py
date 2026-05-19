from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from src.access_logs.models import AccessLog
from src.access_logs.schemas import AccessLogCreate
from src.doors.models import Door


async def _create_door(session: AsyncSession, name: str = "front_gate") -> Door:
    door = Door(name=name, mqtt_id=name)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


@pytest.mark.asyncio
async def test_create_access_log_persists_and_returns_log(
    database_session: AsyncSession,
) -> None:
    from src.access_logs.service import create_access_log

    door = await _create_door(database_session)
    user_id = uuid4()
    timestamp = datetime(2026, 5, 19, 8, 30, 0)

    access_log = await create_access_log(
        AccessLogCreate(
            timestamp=timestamp,
            door_id=door.id,
            user_id=user_id,
            username="alice",
            confidence=0.91,
            door_opened=True,
        ),
        database_session,
    )

    assert access_log.id is not None
    assert access_log.timestamp == timestamp
    assert access_log.door_id == door.id
    assert access_log.user_id == user_id
    assert access_log.username == "alice"
    assert access_log.confidence == 0.91
    assert access_log.door_opened is True


def test_access_log_create_requires_door_id() -> None:
    with pytest.raises(ValidationError):
        AccessLogCreate.model_validate({"door_opened": True})


@pytest.mark.asyncio
async def test_list_access_logs_returns_newest_first(
    database_session: AsyncSession,
) -> None:
    from src.access_logs.service import list_access_logs

    door = await _create_door(database_session)
    older = AccessLog(
        timestamp=datetime(2026, 5, 19, 8, 0, 0),
        door_id=door.id,
        username="older",
        door_opened=True,
    )
    newer = AccessLog(
        timestamp=datetime(2026, 5, 19, 8, 0, 0) + timedelta(minutes=5),
        door_id=door.id,
        username="newer",
        door_opened=False,
    )
    database_session.add(older)
    database_session.add(newer)
    await database_session.commit()

    total, logs = await list_access_logs(database_session, skip=0, limit=10)

    assert total >= 2
    assert [log.username for log in logs[:2]] == ["newer", "older"]


@pytest.mark.asyncio
async def test_list_access_logs_pagination_respects_skip_and_limit(
    database_session: AsyncSession,
) -> None:
    from src.access_logs.service import list_access_logs

    door = await _create_door(database_session)
    for index in range(3):
        database_session.add(
            AccessLog(
                timestamp=datetime(2026, 5, 19, 8, index, 0),
                door_id=door.id,
                username=f"user_{index}",
                door_opened=True,
            )
        )
    await database_session.commit()

    total, logs = await list_access_logs(database_session, skip=1, limit=1)

    assert total >= 3
    assert len(logs) == 1
    assert logs[0].username == "user_1"
