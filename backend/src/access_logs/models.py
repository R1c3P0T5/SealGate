from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class AccessLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    timestamp: datetime = Field(default_factory=utc_now_naive, nullable=False)
    door_id: UUID = Field(foreign_key="door.id", index=True, nullable=False)
    user_id: UUID | None = Field(default=None, index=True)
    username: str | None = Field(default=None, max_length=128)
    confidence: float | None = Field(default=None)
    door_opened: bool = Field(nullable=False)
