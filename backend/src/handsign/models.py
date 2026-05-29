from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel

from src.core.utils import utc_now_naive


class Jutsu(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True, nullable=False, max_length=128)
    signs: list[str] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)


class DoorJutsu(SQLModel, table=True):
    __tablename__: str = "door_jutsu"  # type: ignore[assignment]

    door_id: UUID = Field(foreign_key="door.id", primary_key=True)
    jutsu_id: UUID = Field(foreign_key="jutsu.id", primary_key=True)


class UserJutsuPermission(SQLModel, table=True):
    __tablename__: str = "userjutsupermission"  # type: ignore[assignment]

    user_id: UUID = Field(foreign_key="user.id", primary_key=True)
    jutsu_id: UUID = Field(foreign_key="jutsu.id", primary_key=True, index=True)
    action: str = Field(primary_key=True, max_length=32)
    created_at: datetime = Field(default_factory=utc_now_naive, nullable=False)
