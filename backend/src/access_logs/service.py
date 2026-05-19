from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.access_logs.models import AccessLog
from src.access_logs.schemas import AccessLogCreate


async def create_access_log(
    request: AccessLogCreate,
    session: AsyncSession,
) -> AccessLog:
    access_log = AccessLog(
        timestamp=request.timestamp,
        door_id=request.door_id,
        user_id=request.user_id,
        username=request.username,
        confidence=request.confidence,
        door_opened=request.door_opened,
    )
    session.add(access_log)
    await session.commit()
    await session.refresh(access_log)
    return access_log


async def list_access_logs(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> tuple[int, list[AccessLog]]:
    total = (await session.exec(select(func.count()).select_from(AccessLog))).one()
    logs = list(
        (
            await session.exec(
                select(AccessLog)
                .order_by(col(AccessLog.timestamp).desc())
                .offset(skip)
                .limit(limit)
            )
        ).all()
    )
    return total, logs
