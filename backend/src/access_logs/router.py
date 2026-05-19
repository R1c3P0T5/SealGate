from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.access_logs.schemas import AccessLogListResponse, AccessLogResponse
from src.access_logs.service import list_access_logs
from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.users.models import User


router = APIRouter(prefix="/api/access-logs", tags=["access-logs"])


@router.get(
    "",
    response_model=AccessLogListResponse,
    summary="List access logs",
    description="Return a paginated audit log of door access events.",
)
async def list_access_logs_endpoint(
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("log:read"))],
    skip: Annotated[int, Query(ge=0, description="Access logs to skip.")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum access logs to return.")
    ] = 10,
) -> AccessLogListResponse:
    total, logs = await list_access_logs(session, skip=skip, limit=limit)
    return AccessLogListResponse(
        total=total,
        skip=skip,
        limit=limit,
        logs=[AccessLogResponse.model_validate(log) for log in logs],
    )
