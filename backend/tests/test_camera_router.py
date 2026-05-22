from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

from main import create_app
from src.camera.broker import CameraFrameBroker
from src.core.config import get_settings
from src.core.database import get_session
from src.devices.models import Device
from src.devices.service import hash_device_token
from src.doors.models import Door
from src.ws_tickets.store import WebSocketTicketStore


def _test_app(session: AsyncSession) -> FastAPI:
    app = create_app()
    app.state.ws_ticket_store = WebSocketTicketStore()
    app.state.camera_frame_broker = CameraFrameBroker()

    async def _override() -> AsyncSession:
        return session

    app.dependency_overrides[get_session] = _override
    return app


def _ws_close_code(
    client: TestClient, path: str, *, headers: dict | None = None
) -> int:
    return int(_ws_close(client, path, headers=headers).code)


def _ws_close(
    client: TestClient, path: str, *, headers: dict | None = None
) -> WebSocketDisconnect:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(path, headers=headers or {}) as ws:
            ws.receive_bytes()
    return exc.value


DOOR_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _create_door(session: AsyncSession, *, active: bool = True) -> Door:
    door = Door(
        id=UUID(DOOR_ID), name=f"door-{DOOR_ID}", mqtt_id="door_1", is_active=active
    )
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


async def _create_device_token(session: AsyncSession, door: Door) -> str:
    token = "test-device-token"
    session.add(
        Device(
            name=f"device-{door.id}",
            door_id=door.id,
            token_hash=hash_device_token(token),
        )
    )
    await session.commit()
    return token


@pytest.mark.asyncio
async def test_push_rejects_missing_token(database_session: AsyncSession) -> None:
    await _create_door(database_session)
    client = TestClient(_test_app(database_session))
    assert _ws_close_code(client, f"/ws/camera/{DOOR_ID}/push") == 1008


@pytest.mark.asyncio
async def test_preview_rejects_missing_token(database_session: AsyncSession) -> None:
    await _create_door(database_session)
    client = TestClient(_test_app(database_session))
    assert _ws_close_code(client, f"/ws/camera/{DOOR_ID}/preview") == 1008


@pytest.mark.asyncio
async def test_push_rejects_wrong_device_token(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    await _create_device_token(database_session, door)
    client = TestClient(_test_app(database_session))
    assert (
        _ws_close_code(
            client,
            f"/ws/camera/{DOOR_ID}/push",
            headers={"X-Device-Token": "wrong-token"},
        )
        == 1008
    )


@pytest.mark.asyncio
async def test_preview_rejects_wrong_ticket(
    database_session: AsyncSession,
) -> None:
    await _create_door(database_session)
    client = TestClient(_test_app(database_session))
    assert _ws_close_code(client, f"/ws/camera/{DOOR_ID}/preview?ticket=wrong") == 1008


@pytest.mark.asyncio
async def test_frame_relayed_from_producer_to_viewer(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device_token = await _create_device_token(database_session, door)
    app = _test_app(database_session)
    client = TestClient(app)
    ticket = app.state.ws_ticket_store.issue(
        purpose="camera-preview",
        door_id=DOOR_ID,
        ttl_seconds=30,
    ).ticket

    with client.websocket_connect(
        f"/ws/camera/{DOOR_ID}/preview?ticket={ticket}"
    ) as viewer_ws:
        with client.websocket_connect(
            f"/ws/camera/{DOOR_ID}/push",
            headers={"X-Device-Token": device_token},
        ) as producer_ws:
            start_msg = producer_ws.receive_json()
            assert start_msg == {"type": "start"}

            producer_ws.send_bytes(b"FAKE_JPEG")

            frame = viewer_ws.receive_bytes()
            assert frame == b"FAKE_JPEG"


@pytest.mark.asyncio
async def test_push_rejects_oversized_frame(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    device_token = await _create_device_token(database_session, door)
    app = _test_app(database_session)
    client = TestClient(app)
    max_bytes = get_settings().CAMERA_PREVIEW_MAX_FRAME_BYTES

    with client.websocket_connect(
        f"/ws/camera/{DOOR_ID}/push",
        headers={"X-Device-Token": device_token},
    ) as producer_ws:
        producer_ws.send_bytes(b"0" * (max_bytes + 1))
        with pytest.raises(WebSocketDisconnect) as exc:
            producer_ws.receive_bytes()
        assert exc.value.code == 1009


@pytest.mark.asyncio
async def test_push_rejects_inactive_door(
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session, active=False)
    device_token = await _create_device_token(database_session, door)
    client = TestClient(_test_app(database_session))
    close = _ws_close(
        client,
        f"/ws/camera/{DOOR_ID}/push",
        headers={"X-Device-Token": device_token},
    )
    assert close.code == 1008
    assert close.reason == "Door is inactive"


@pytest.mark.asyncio
async def test_preview_ticket_is_single_use(
    database_session: AsyncSession,
) -> None:
    await _create_door(database_session)
    app = _test_app(database_session)
    client = TestClient(app)
    ticket = app.state.ws_ticket_store.issue(
        purpose="camera-preview",
        door_id=DOOR_ID,
        ttl_seconds=30,
    ).ticket

    with client.websocket_connect(f"/ws/camera/{DOOR_ID}/preview?ticket={ticket}"):
        pass

    assert (
        _ws_close_code(client, f"/ws/camera/{DOOR_ID}/preview?ticket={ticket}") == 1008
    )


@pytest.mark.asyncio
async def test_preview_rejects_inactive_door(
    database_session: AsyncSession,
) -> None:
    await _create_door(database_session, active=False)
    app = _test_app(database_session)
    client = TestClient(app)
    ticket = app.state.ws_ticket_store.issue(
        purpose="camera-preview",
        door_id=DOOR_ID,
        ttl_seconds=30,
    ).ticket

    assert (
        _ws_close_code(client, f"/ws/camera/{DOOR_ID}/preview?ticket={ticket}") == 1008
    )
