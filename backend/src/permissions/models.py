from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Permission(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=64, nullable=False)
    description: str | None = Field(default=None, max_length=256)


class RolePermission(SQLModel, table=True):
    role_id: UUID = Field(foreign_key="role.id", primary_key=True, nullable=False)
    permission_id: UUID = Field(
        foreign_key="permission.id", primary_key=True, nullable=False
    )


class UserPermissionOverride(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    permission_id: UUID = Field(foreign_key="permission.id", nullable=False)
    granted: bool = Field(nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "permission_id"),)
