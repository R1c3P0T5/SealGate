from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class Device(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, nullable=False, max_length=128)
    door_id: UUID = Field(
        foreign_key="door.id",
        index=True,
        nullable=False,
        ondelete="RESTRICT",
    )
    token_hash: str = Field(unique=True, index=True, nullable=False, max_length=64)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
    updated_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
