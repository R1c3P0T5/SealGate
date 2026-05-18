from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    """User registration request."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=32,
        description="Unique login name for the new account.",
        examples=["operator01"],
    )
    password: str = Field(
        ...,
        min_length=12,
        description=(
            "Plain-text password used only for registration. It is hashed before "
            "storage and must satisfy the password strength policy."
        ),
        examples=["StrongPassword123"],
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable display name for the account.",
        examples=["Camera Operator"],
    )
    email: EmailStr | None = Field(
        default=None,
        description="Optional unique email address for the account.",
        examples=["operator01@example.com"],
    )


class UserLoginRequest(BaseModel):
    """User login request."""

    username: str = Field(
        ...,
        description="Username registered for the account.",
        examples=["operator01"],
    )
    password: str = Field(
        ...,
        description="Plain-text account password.",
        examples=["StrongPassword123"],
    )


class UserResponse(BaseModel):
    """Safe user data for API responses."""

    id: UUID = Field(description="Stable user identifier.")
    username: str = Field(description="Unique login name.")
    email: str | None = Field(default=None, description="Optional email address.")
    full_name: str = Field(description="Human-readable display name.")
    role_name: str = Field(description="Role name assigned to the user.")
    is_active: bool = Field(description="Whether the account can authenticate.")
    created_at: datetime = Field(description="UTC timestamp when the user was created.")

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    """Login response with JWT access token."""

    access_token: str = Field(description="JWT bearer token for authenticated calls.")
    token_type: str = Field(
        default="bearer", description="Token type for OAuth2 usage."
    )
    user: UserResponse = Field(description="Authenticated user's safe profile.")


class TokenResponse(BaseModel):
    """OAuth2-compatible token response."""

    access_token: str = Field(description="JWT bearer token for authenticated calls.")
    token_type: str = Field(
        default="bearer", description="Token type for OAuth2 usage."
    )
