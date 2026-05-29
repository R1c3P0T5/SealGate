import logging
from typing import Any

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.access_logs.models import AccessLog
from src.access_logs.schemas import AccessLogCreate


async def record_access_event(
    log_create: AccessLogCreate,
    session: AsyncSession,
    broker: Any,
    logger: logging.Logger,
) -> "AccessLog | None":
    """Create an access log entry and publish it to the event broker.

    Returns the created AccessLog on success, or None on failure.
    Rolls back the session on DB error so the connection is returned clean.
    """
    from src.access_logs.schemas import AccessLogResponse

    try:
        log = await create_access_log(log_create, session)
        await broker.publish(AccessLogResponse.model_validate(log))
        return log
    except Exception:
        await session.rollback()
        logger.warning("Failed to write access log for door %s", log_create.door_id)
        return None


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
