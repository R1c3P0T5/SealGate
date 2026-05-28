from collections.abc import AsyncGenerator
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.core.database import get_session
from src.handsign.registry import HandsignFSMRegistry
from src.handsign.router import handsign_feed_router


@pytest.fixture
def app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(handsign_feed_router)

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


def _door(door_id: UUID, auth_mode: str) -> SimpleNamespace:
    return SimpleNamespace(id=door_id, auth_mode=auth_mode)


def _device(door_id: UUID) -> SimpleNamespace:
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

    async def get_device_by_token_hash(token_hash: str, session: object) -> object:
        return _device(door_id)

    async def get_door_by_id(lookup_id: UUID, session: object) -> object:
        assert lookup_id == door_id
        return _door(door_id, "face")

    import src.devices.service as devices_service
    import src.doors.service as doors_service

    monkeypatch.setattr(
        devices_service, "get_device_by_token_hash", get_device_by_token_hash
    )
    monkeypatch.setattr(doors_service, "get_door_by_id", get_door_by_id)

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

    async def get_device_by_token_hash(token_hash: str, session: object) -> object:
        return _device(door_id)

    async def get_door_by_id(lookup_id: UUID, session: object) -> object:
        assert lookup_id == door_id
        return _door(door_id, "handsign")

    import src.devices.service as devices_service
    import src.doors.service as doors_service
    import src.handsign.router as handsign_router

    monkeypatch.setattr(
        devices_service, "get_device_by_token_hash", get_device_by_token_hash
    )
    monkeypatch.setattr(doors_service, "get_door_by_id", get_door_by_id)
    monkeypatch.setattr(handsign_router, "get_registry", lambda: registry)

    response = await client.post(
        f"/api/doors/{door_id}/handsign/feed",
        json={"sign": "i", "timestamp": 1.0},
        headers=_device_auth(),
    )

    assert response.status_code == 200
    assert response.json() == {"step": 1, "total": 2, "completed": False}
