from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class FaceVector(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, nullable=False)
    embedding: bytes = Field(nullable=False)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
