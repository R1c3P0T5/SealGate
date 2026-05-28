from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ChangePasswordRequest(BaseModel):
    """Password change request."""

    current_password: str | None = Field(
        default=None,
        description="Current password. Required when changing your own password.",
    )
    new_password: str = Field(description="New password.")


class UserUpdateRequest(BaseModel):
    """User profile update request."""

    full_name: str | None = Field(
        None,
        max_length=255,
        description="Optional replacement display name.",
        examples=["Updated Operator"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional replacement email address.",
        examples=["updated.operator@example.com"],
    )


class SetUserActiveRequest(BaseModel):
    """Admin-only request to toggle a user's active flag."""

    is_active: bool = Field(description="Whether the account can authenticate.")


class SetUserDoorAccessRequest(BaseModel):
    """Admin-only request to replace doors a user may unlock."""

    door_ids: list[UUID] = Field(description="Door IDs the user may unlock.")


class UserDoorAccessResponse(BaseModel):
    """Doors a user may unlock."""

    door_ids: list[UUID] = Field(description="Door IDs the user may unlock.")


class UserResponseFull(BaseModel):
    """Full user information for admin responses."""

    id: UUID = Field(description="Stable user identifier.")
    username: str = Field(description="Unique login name.")
    email: str | None = Field(default=None, description="Optional email address.")
    full_name: str = Field(description="Human-readable display name.")
    role_name: str = Field(description="Role name assigned to the user.")
    is_active: bool = Field(description="Whether the account can authenticate.")
    created_at: datetime = Field(description="UTC timestamp when the user was created.")
    updated_at: datetime = Field(
        description="UTC timestamp for the latest profile change."
    )

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    """Paginated user list response."""

    total: int = Field(..., ge=0, description="Total users matching the query.")
    skip: int = Field(..., ge=0, description="Number of skipped users.")
    limit: int = Field(..., ge=1, description="Maximum users requested.")
    users: list[UserResponseFull] = Field(description="Users in the current page.")
