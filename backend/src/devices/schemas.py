from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeviceCreateRequest(BaseModel):
    name: str = Field(max_length=128, description="Unique device display name.")
    door_id: UUID = Field(description="Door this device is allowed to operate.")
    is_active: bool = Field(default=True, description="Whether the device may connect.")


class DeviceUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, max_length=128, description="Replacement display name."
    )
    door_id: UUID | None = Field(
        default=None, description="Replacement door this device is allowed to operate."
    )
    is_active: bool | None = Field(default=None, description="Replacement active flag.")


class DeviceResponse(BaseModel):
    id: UUID = Field(description="Stable device identifier.")
    name: str = Field(description="Device display name.")
    door_id: UUID = Field(description="Door this device is allowed to operate.")
    is_active: bool = Field(description="Whether the device may connect.")
    created_at: datetime = Field(
        description="UTC timestamp when the device was created."
    )
    updated_at: datetime = Field(
        description="UTC timestamp when the device was updated."
    )

    model_config = {"from_attributes": True}


class DeviceCreateResponse(DeviceResponse):
    token: str = Field(description="One-time plaintext device token.")


class DeviceRotateTokenResponse(DeviceResponse):
    token: str = Field(description="One-time plaintext replacement device token.")


class DeviceListResponse(BaseModel):
    total: int = Field(..., ge=0, description="Total devices matching the query.")
    skip: int = Field(..., ge=0, description="Number of skipped devices.")
    limit: int = Field(..., ge=1, description="Maximum devices requested.")
    devices: list[DeviceResponse] = Field(description="Devices in the current page.")
