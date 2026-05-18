from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class User(SQLModel, table=True):
    """User database model for authentication and profile management."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, nullable=False)
    email: str | None = Field(default=None, unique=True, index=True)
    password_hash: str = Field(nullable=False)
    full_name: str = Field(nullable=False)
    role_id: UUID = Field(foreign_key="role.id", index=True, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
