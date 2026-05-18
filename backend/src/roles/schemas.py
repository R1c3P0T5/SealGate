from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime


class RoleListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    roles: list[RoleResponse]


class PermissionSummary(BaseModel):
    id: UUID
    name: str
    description: str | None


class RolePermissionsResponse(BaseModel):
    role_id: UUID
    permissions: list[PermissionSummary]


class RoleUsersResponse(BaseModel):
    role_id: UUID
    total: int
    skip: int
    limit: int
    user_ids: list[UUID]
