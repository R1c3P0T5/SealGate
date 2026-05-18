from typing import Annotated

from fastapi import APIRouter, Depends

from src.auth.dependencies import get_current_user
from src.core.database import SessionDep
from src.permissions.schemas import PermissionResponse, PermissionsListResponse
from src.permissions.service import all_permissions
from src.users.models import User

router = APIRouter(prefix="/api/permissions", tags=["permissions"])


@router.get("", response_model=PermissionsListResponse)
async def list_permissions(
    session: SessionDep,
    current_user: Annotated[User, Depends(get_current_user)],
) -> PermissionsListResponse:
    perms = await all_permissions(session)
    return PermissionsListResponse(
        permissions=[
            PermissionResponse(name=p.name, description=p.description) for p in perms
        ]
    )
