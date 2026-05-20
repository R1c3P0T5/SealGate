from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


_MQTT_ID_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


class DoorCreateRequest(BaseModel):
    name: str = Field(max_length=128, description="Unique display name.")
    mqtt_id: str = Field(
        max_length=64,
        pattern=_MQTT_ID_PATTERN,
        description="Unique MQTT topic slug (lowercase, alphanumeric, hyphens, underscores).",
    )
    location: str | None = Field(
        default=None, max_length=256, description="Optional physical location."
    )
    is_active: bool = Field(
        default=True, description="Whether the door is operational."
    )


class DoorUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, max_length=128, description="Replacement display name."
    )
    mqtt_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=_MQTT_ID_PATTERN,
        description="Replacement MQTT topic slug.",
    )
    location: str | None = Field(
        default=None, max_length=256, description="Replacement location."
    )
    is_active: bool | None = Field(default=None, description="Replacement active flag.")


class DoorResponse(BaseModel):
    id: UUID = Field(description="Stable door identifier.")
    name: str = Field(description="Display name.")
    mqtt_id: str | None = Field(default=None, description="MQTT topic slug.")
    location: str | None = Field(default=None, description="Physical location.")
    is_active: bool = Field(description="Whether the door is operational.")
    created_at: datetime = Field(description="UTC timestamp when the door was created.")

    model_config = {"from_attributes": True}


class DoorUnlockResponse(BaseModel):
    door_id: UUID = Field(description="Door that received the unlock command.")
    user_id: UUID = Field(description="User who requested the unlock.")
    username: str = Field(description="Username snapshot for the unlock request.")
    confidence: float | None = Field(
        default=None, description="Recognition confidence, if applicable."
    )
    door_opened: bool = Field(description="Whether the backend sent an open command.")
    access_log_id: UUID | None = Field(
        default=None, description="Access log entry written for this unlock."
    )


class DoorListResponse(BaseModel):
    total: int = Field(..., ge=0, description="Total doors matching the query.")
    skip: int = Field(..., ge=0, description="Number of skipped doors.")
    limit: int = Field(..., ge=1, description="Maximum doors requested.")
    doors: list[DoorResponse] = Field(description="Doors in the current page.")
