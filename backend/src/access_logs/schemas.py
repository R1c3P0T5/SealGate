from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from src.core.utils import utc_now_naive


class AccessLogCreate(BaseModel):
    timestamp: datetime = Field(
        default_factory=utc_now_naive,
        description="UTC timestamp when the access event happened.",
    )
    door_id: UUID = Field(description="Door associated with the access event.")
    user_id: UUID | None = Field(
        default=None, description="Matched or acting user identifier, if available."
    )
    username: str | None = Field(
        default=None, max_length=128, description="Username snapshot, if available."
    )
    confidence: float | None = Field(
        default=None, description="Recognition confidence, if applicable."
    )
    door_opened: bool = Field(description="Whether the backend sent an open command.")


class AccessLogResponse(BaseModel):
    id: UUID = Field(description="Stable access log identifier.")
    timestamp: datetime = Field(description="UTC timestamp when the event happened.")
    door_id: UUID = Field(description="Door associated with the access event.")
    user_id: UUID | None = Field(
        default=None, description="Matched or acting user identifier, if available."
    )
    username: str | None = Field(
        default=None, description="Username snapshot, if available."
    )
    confidence: float | None = Field(
        default=None, description="Recognition confidence, if applicable."
    )
    door_opened: bool = Field(description="Whether the backend sent an open command.")

    model_config = {"from_attributes": True}

    @field_serializer("timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")


class AccessLogListResponse(BaseModel):
    total: int = Field(..., ge=0, description="Total access logs matching the query.")
    skip: int = Field(..., ge=0, description="Number of skipped logs.")
    limit: int = Field(..., ge=1, description="Maximum logs requested.")
    logs: list[AccessLogResponse] = Field(description="Logs in the current page.")
