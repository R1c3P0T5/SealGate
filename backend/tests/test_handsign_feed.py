from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.database import get_session
from src.handsign.registry import HandsignFSMRegistry
from src.handsign.router import handsign_feed_router


def _mock_camera_broker() -> MagicMock:
    broker = MagicMock()
    broker.relay_metadata = AsyncMock()
    return broker


def _mock_access_broker() -> MagicMock:
    broker = MagicMock()
    broker.publish = AsyncMock()
    return broker


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(handsign_feed_router)
    test_app.state.camera_frame_broker = _mock_camera_broker()

    async def override_get_session() -> AsyncGenerator[object, None]:
        yield object()

    test_app.dependency_overrides[get_session] = override_get_session
    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client


def _door(door_id: UUID, auth_mode: str) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(id=door_id, auth_mode=auth_mode, is_active=True)


def _device(door_id: UUID) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(door_id=door_id, is_active=True)


def _device_auth(token: str = "handsign-device-token") -> dict[str, str]:
    return {"X-Device-Token": token}


@pytest.mark.asyncio
async def test_feed_missing_token(client: AsyncClient) -> None:
    response = await client.post(
        f"/api/doors/{uuid4()}/handsign/feed",
        json={"sign": "i", "timestamp": 1.0},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feed_door_without_handsign_mode(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door_id = uuid4()

    import src.devices.auth as devices_auth

    async def get_device_by_token_hash(token_hash: str, session: object) -> object:
        return _device(door_id)

    async def get_door_by_id(lookup_id: UUID, session: object) -> object:
        assert lookup_id == door_id
        return _door(door_id, "face")

    monkeypatch.setattr(
        devices_auth, "get_device_by_token_hash", get_device_by_token_hash
    )
    monkeypatch.setattr(devices_auth, "get_door_by_id", get_door_by_id)

    response = await client.post(
        f"/api/doors/{door_id}/handsign/feed",
        json={"sign": "i", "timestamp": 1.0},
        headers=_device_auth(),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_feed_returns_progress(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door_id = uuid4()
    registry = HandsignFSMRegistry()
    registry.load(door_id, {"火遁・豪火球の術": ["亥", "寅"]})

    import src.devices.auth as devices_auth
    import src.handsign.router as handsign_router

    async def get_device_by_token_hash(token_hash: str, session: object) -> object:
        return _device(door_id)

    async def get_door_by_id(lookup_id: UUID, session: object) -> object:
        assert lookup_id == door_id
        return _door(door_id, "handsign")

    monkeypatch.setattr(
        devices_auth, "get_device_by_token_hash", get_device_by_token_hash
    )
    monkeypatch.setattr(devices_auth, "get_door_by_id", get_door_by_id)
    monkeypatch.setattr(handsign_router, "get_registry", lambda: registry)

    response = await client.post(
        f"/api/doors/{door_id}/handsign/feed",
        json={"sign": "i", "timestamp": 1.0},
        headers=_device_auth(),
    )

    assert response.status_code == 200
    assert response.json() == {"step": 1, "total": 2, "completed": False}


@pytest.mark.asyncio
async def test_feed_handsign_mode_creates_access_log(
    app: FastAPI,
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    door_id = uuid4()
    # One-step jutsu so a single feed completes it
    registry = HandsignFSMRegistry()
    registry.load(door_id, {"一刀流": ["亥"]})

    access_broker = _mock_access_broker()
    app.state.access_event_broker = access_broker

    import src.devices.auth as devices_auth
    import src.doors.mqtt as doors_mqtt
    import src.handsign.router as handsign_router

    async def get_device_by_token_hash(token_hash: str, session: object) -> object:
        return _device(door_id)

    async def get_door_by_id(lookup_id: UUID, session: object) -> object:
        assert lookup_id == door_id
        return _door(door_id, "handsign")

    from src.access_logs.schemas import AccessLogCreate as _ALC

    created_logs: list[_ALC] = []

    async def mock_publish_door_unlock(door: object) -> None:
        pass

    async def mock_create_access_log(log_create: _ALC, session: object) -> object:
        created_logs.append(log_create)
        import datetime
        import uuid
        from types import SimpleNamespace

        return SimpleNamespace(
            id=uuid.uuid4(),
            door_id=door_id,
            user_id=None,
            username=None,
            confidence=None,
            door_opened=True,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        )

    monkeypatch.setattr(
        devices_auth, "get_device_by_token_hash", get_device_by_token_hash
    )
    monkeypatch.setattr(devices_auth, "get_door_by_id", get_door_by_id)
    monkeypatch.setattr(handsign_router, "get_registry", lambda: registry)
    monkeypatch.setattr(doors_mqtt, "publish_door_unlock", mock_publish_door_unlock)
    monkeypatch.setattr(handsign_router, "create_access_log", mock_create_access_log)

    response = await client.post(
        f"/api/doors/{door_id}/handsign/feed",
        json={"sign": "i", "timestamp": 1.0},
        headers=_device_auth(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completed"] is True
    assert len(created_logs) == 1
    log = created_logs[0]
    assert log.door_id == door_id
    assert log.door_opened is True
