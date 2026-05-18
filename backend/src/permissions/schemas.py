from uuid import UUID

from pydantic import BaseModel


class PermissionResponse(BaseModel):
    name: str
    description: str | None


class PermissionsListResponse(BaseModel):
    permissions: list[PermissionResponse]


class PermissionOverride(BaseModel):
    permission: str
    granted: bool


class UserPermissionsResponse(BaseModel):
    effective: list[str]
    role_permissions: list[str]
    overrides: list[PermissionOverride]


class SetUserPermissionsRequest(BaseModel):
    overrides: list[PermissionOverride]


class SetUserRoleRequest(BaseModel):
    role_id: UUID
