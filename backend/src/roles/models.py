from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class Role(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=64, nullable=False)
    description: str | None = Field(default=None, max_length=256)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
