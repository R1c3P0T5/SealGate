from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status

from src.auth.dependencies import require_permission
from src.core.database import SessionDep
from src.devices.schemas import (
    DeviceCreateRequest,
    DeviceCreateResponse,
    DeviceListResponse,
    DeviceResponse,
    DeviceRotateTokenResponse,
    DeviceUpdateRequest,
)
from src.devices.service import (
    create_device,
    delete_device,
    get_device_by_id,
    list_devices,
    rotate_device_token,
    to_device_response,
    update_device,
)
from src.users.models import User


router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get(
    "",
    response_model=DeviceListResponse,
    summary="List devices",
    description="Return a paginated list of camera devices.",
)
async def list_devices_endpoint(
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
    skip: Annotated[int, Query(ge=0, description="Devices to skip.")] = 0,
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum devices to return.")
    ] = 10,
) -> DeviceListResponse:
    total, devices = await list_devices(session, skip=skip, limit=limit)
    return DeviceListResponse(
        total=total,
        skip=skip,
        limit=limit,
        devices=[to_device_response(device) for device in devices],
    )


@router.post(
    "",
    response_model=DeviceCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create device",
    description="Create a camera device and return its one-time token.",
)
async def create_device_endpoint(
    request: DeviceCreateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
) -> DeviceCreateResponse:
    device, token = await create_device(request, session)
    response = to_device_response(device)
    return DeviceCreateResponse(**response.model_dump(), token=token)


@router.get(
    "/{device_id}",
    response_model=DeviceResponse,
    summary="Get device",
    description="Return a single camera device by ID.",
)
async def get_device_endpoint(
    device_id: Annotated[UUID, Path(description="Device ID to fetch.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
) -> DeviceResponse:
    device = await get_device_by_id(device_id, session)
    return to_device_response(device)


@router.put(
    "/{device_id}",
    response_model=DeviceResponse,
    summary="Update device",
    description="Update camera device fields without rotating its token.",
)
async def update_device_endpoint(
    device_id: Annotated[UUID, Path(description="Device ID to update.")],
    request: DeviceUpdateRequest,
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
) -> DeviceResponse:
    device = await update_device(device_id, request, session)
    return to_device_response(device)


@router.delete(
    "/{device_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete device",
    description="Delete a camera device.",
)
async def delete_device_endpoint(
    device_id: Annotated[UUID, Path(description="Device ID to delete.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
) -> None:
    await delete_device(device_id, session)


@router.post(
    "/{device_id}/rotate-token",
    response_model=DeviceRotateTokenResponse,
    summary="Rotate device token",
    description="Replace a camera device token and return the new one-time token.",
)
async def rotate_device_token_endpoint(
    device_id: Annotated[UUID, Path(description="Device ID to rotate.")],
    session: SessionDep,
    current_user: Annotated[User, Depends(require_permission("device:manage"))],
) -> DeviceRotateTokenResponse:
    device, token = await rotate_device_token(device_id, session)
    response = to_device_response(device)
    return DeviceRotateTokenResponse(**response.model_dump(), token=token)
