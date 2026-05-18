from collections.abc import AsyncGenerator
from unittest.mock import MagicMock
from uuid import uuid4

import cv2
import numpy as np
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.websockets import WebSocketDisconnect

import src.core.database as db
from src.auth.utils import create_access_token, hash_password
from src.core.config import get_settings
from src.core.database import get_session
from src.faces.engine import get_engine
from src.faces.service import add_face_vector
from src.users.models import User, UserRole

MOCK_EMBEDDING = np.random.default_rng(42).random(128, dtype=np.float32).tobytes()
TEST_DEVICE_TOKEN = "test-jetson-device-token"
WEBSOCKET_RECOGNIZE_PATH = "/ws/faces/recognize"
DEVICE_AUTH_HEADERS = {"Authorization": f"Bearer {TEST_DEVICE_TOKEN}"}


def _make_jpeg_bytes() -> bytes:
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


async def _create_user_with_token(
    session: AsyncSession,
    *,
    role: UserRole = UserRole.USER,
) -> tuple[User, str]:
    user = User(
        username=f"user_{uuid4().hex[:12]}",
        email=f"{uuid4().hex[:12]}@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Face Router User",
        role=role,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user.id)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_bearer_token_parses_authorization_header() -> None:
    from src.faces.router import _bearer_token

    assert _bearer_token("Bearer camera-token") == "camera-token"
    assert _bearer_token("bearer camera-token") == "camera-token"
    assert _bearer_token("Basic camera-token") is None
    assert _bearer_token("Bearer") is None
    assert _bearer_token(None) is None


async def _create_websocket_user_with_face(engine: AsyncEngine) -> User:
    async with AsyncSession(
        engine,
        expire_on_commit=False,
        autoflush=False,
    ) as session:
        user, _ = await _create_user_with_token(session)
        await add_face_vector(user.id, MOCK_EMBEDDING, "front", session)
        return user


@pytest_asyncio.fixture
async def client_with_face(
    database_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    from main import app

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield database_session

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_engine] = lambda: engine

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def websocket_client(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[TestClient, None]:
    from main import app

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(
        db,
        "async_session",
        async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        ),
    )

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def websocket_client_with_mock_engine(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[TestClient, None]:
    from main import app

    mock_engine = MagicMock()
    mock_engine.detect_and_embed.return_value = MOCK_EMBEDDING

    monkeypatch.setattr(db, "engine", engine)
    monkeypatch.setattr(
        db,
        "async_session",
        async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        ),
    )

    app.dependency_overrides[get_engine] = lambda: mock_engine

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_faces_empty_returns_total_and_faces(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)

    response = await client.get(
        f"/api/users/{user.id}/faces",
        headers=_auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["faces"] == []
    assert data["skip"] == 0
    assert data["limit"] == 100


@pytest.mark.asyncio
async def test_list_faces_requires_authentication(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, _ = await _create_user_with_token(database_session)

    response = await client.get(f"/api/users/{user.id}/faces")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_faces_forbids_other_user(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, _ = await _create_user_with_token(database_session)
    other_user, other_token = await _create_user_with_token(database_session)

    response = await client.get(
        f"/api/users/{user.id}/faces",
        headers=_auth_headers(other_token),
    )

    assert other_user.id != user.id
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_faces_for_any_user(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, _ = await _create_user_with_token(database_session)
    _, admin_token = await _create_user_with_token(
        database_session,
        role=UserRole.ADMIN,
    )

    response = await client.get(
        f"/api/users/{user.id}/faces",
        headers=_auth_headers(admin_token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["faces"] == []
    assert data["skip"] == 0
    assert data["limit"] == 100


@pytest.mark.asyncio
async def test_delete_face_returns_no_content_after_adding(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)
    face = await add_face_vector(user.id, MOCK_EMBEDDING, "front", database_session)

    response = await client.delete(
        f"/api/users/{user.id}/faces/{face.id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_delete_nonexistent_face_returns_not_found(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)

    response = await client.delete(
        f"/api/users/{user.id}/faces/{uuid4()}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Face vector not found"


@pytest.mark.asyncio
async def test_from_image_register_no_face_returns_400(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)

    response = await client.post(
        f"/api/users/{user.id}/faces/from-image",
        files={"image": ("face.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No face detected in the provided image"


@pytest.mark.asyncio
async def test_from_image_register_invalid_image_returns_400(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)

    response = await client.post(
        f"/api/users/{user.id}/faces/from-image",
        files={"image": ("face.jpg", b"not an image", "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Could not decode the provided image"


@pytest.mark.asyncio
async def test_from_image_register_with_face_stores_embedding(
    client_with_face: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, token = await _create_user_with_token(database_session)

    response = await client_with_face.post(
        f"/api/users/{user.id}/faces/from-image",
        files={"image": ("face.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["embedding_size"] == 512
    assert data["id"]
    assert data["created_at"]


@pytest.mark.asyncio
async def test_add_face_from_image_offloads_face_engine_to_threadpool(
    client_with_face: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.faces.router as router

    user, token = await _create_user_with_token(database_session)
    threadpool_calls = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        threadpool_calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(router, "run_in_threadpool", fake_run_in_threadpool)

    response = await client_with_face.post(
        f"/api/users/{user.id}/faces/from-image",
        files={"image": ("face.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_auth_headers(token),
    )

    assert response.status_code == 201
    assert threadpool_calls


@pytest.mark.asyncio
async def test_recognize_from_image_no_face_returns_400(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/faces/recognize/from-image",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "No face detected in the provided image"


@pytest.mark.asyncio
async def test_recognize_from_image_requires_no_auth(
    client_with_face: AsyncClient,
) -> None:
    response = await client_with_face.post(
        "/api/faces/recognize/from-image",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_recognize_from_image_matched(
    client_with_face: AsyncClient,
    database_session: AsyncSession,
) -> None:
    user, _ = await _create_user_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, "front", database_session)

    response = await client_with_face.post(
        "/api/faces/recognize/from-image",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["user_id"] == str(user.id)
    assert data["username"] == user.username
    assert data["confidence"] == pytest.approx(1.0, abs=1e-5)


@pytest.mark.asyncio
async def test_recognize_image_bytes_offloads_face_engine_to_threadpool(
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.faces.router as router

    user, _ = await _create_user_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, "front", database_session)
    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    threadpool_calls = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        threadpool_calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(
        router,
        "run_in_threadpool",
        fake_run_in_threadpool,
    )

    response = await router._recognize_image_bytes(
        _make_jpeg_bytes(),
        database_session,
        engine,
        threshold=0.363,
    )

    assert response.matched is True
    assert threadpool_calls


@pytest.mark.asyncio
async def test_recognize_websocket_matched(
    websocket_client_with_mock_engine: TestClient,
    engine: AsyncEngine,
) -> None:
    user = await _create_websocket_user_with_face(engine)

    with websocket_client_with_mock_engine.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(_make_jpeg_bytes())
        data = ws.receive_json()

    assert data["type"] == "result"
    assert data["matched"] is True
    assert data["user_id"] == str(user.id)
    assert data["username"] == user.username
    assert data["confidence"] == pytest.approx(1.0, abs=1e-5)


@pytest.mark.asyncio
async def test_recognize_websocket_no_face_keeps_connection(
    websocket_client: TestClient,
) -> None:
    with websocket_client.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(_make_jpeg_bytes())
        no_face = ws.receive_json()
        ws.send_text("not binary")
        unsupported = ws.receive_json()

    assert no_face == {
        "type": "error",
        "error": "no_face_detected",
        "detail": "No face detected in the provided image",
    }
    assert unsupported == {
        "type": "error",
        "error": "unsupported_message",
        "detail": "Send image frames as binary WebSocket messages",
    }


@pytest.mark.asyncio
async def test_recognize_websocket_invalid_image_keeps_connection(
    websocket_client_with_mock_engine: TestClient,
) -> None:
    with websocket_client_with_mock_engine.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(b"not an image")
        invalid = ws.receive_json()
        ws.send_text("not binary")
        unsupported = ws.receive_json()

    assert invalid == {
        "type": "error",
        "error": "invalid_image",
        "detail": "Could not decode the provided image",
    }
    assert unsupported["error"] == "unsupported_message"


@pytest.mark.asyncio
async def test_recognize_websocket_handles_multiple_frames(
    websocket_client_with_mock_engine: TestClient,
    engine: AsyncEngine,
) -> None:
    user = await _create_websocket_user_with_face(engine)

    with websocket_client_with_mock_engine.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(_make_jpeg_bytes())
        first = ws.receive_json()
        ws.send_bytes(_make_jpeg_bytes())
        second = ws.receive_json()

    assert first["type"] == "result"
    assert second["type"] == "result"
    assert first["matched"] is True
    assert second["matched"] is True
    assert first["user_id"] == second["user_id"] == str(user.id)


@pytest.mark.asyncio
async def test_recognize_websocket_rejects_oversized_image(
    websocket_client: TestClient,
) -> None:
    max_image_bytes = get_settings().WEBSOCKET_MAX_IMAGE_BYTES

    with websocket_client.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(b"0" * (max_image_bytes + 1))
        data = ws.receive_json()

    assert data == {
        "type": "error",
        "error": "image_too_large",
        "detail": f"WebSocket image frame exceeds the {max_image_bytes} byte limit",
    }


@pytest.mark.asyncio
async def test_recognize_websocket_unexpected_error_keeps_connection(
    websocket_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from main import app

    mock_engine = MagicMock()
    mock_engine.detect_and_embed.side_effect = RuntimeError("model unavailable")
    app.dependency_overrides[get_engine] = lambda: mock_engine

    with websocket_client.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(_make_jpeg_bytes())
        error = ws.receive_json()
        ws.send_text("not binary")
        unsupported = ws.receive_json()

    assert error == {
        "type": "error",
        "error": "recognition_failed",
        "detail": "Face recognition failed",
    }
    assert unsupported["error"] == "unsupported_message"
    assert "Face recognition WebSocket frame failed" in caplog.text
    assert "RuntimeError: model unavailable" in caplog.text


@pytest.mark.asyncio
async def test_recognize_websocket_offloads_face_engine_to_threadpool(
    websocket_client_with_mock_engine: TestClient,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.faces.router as router

    await _create_websocket_user_with_face(engine)
    threadpool_calls = []

    async def fake_run_in_threadpool(func, *args, **kwargs):
        threadpool_calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(router, "run_in_threadpool", fake_run_in_threadpool)

    with websocket_client_with_mock_engine.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        ws.send_bytes(_make_jpeg_bytes())
        data = ws.receive_json()

    assert data["type"] == "result"
    assert threadpool_calls


@pytest.mark.asyncio
async def test_recognize_websocket_requires_device_token(
    websocket_client: TestClient,
) -> None:
    with websocket_client.websocket_connect("/ws/faces/recognize") as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_recognize_websocket_rejects_invalid_device_token(
    websocket_client: TestClient,
) -> None:
    with websocket_client.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers={"Authorization": "Bearer wrong-token"},
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_recognize_websocket_rejects_when_device_token_unconfigured(
    websocket_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JETSON_CAMERA_TOKEN", raising=False)
    get_settings.cache_clear()

    with websocket_client.websocket_connect(
        WEBSOCKET_RECOGNIZE_PATH,
        headers=DEVICE_AUTH_HEADERS,
    ) as ws:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            ws.receive_json()

    assert exc_info.value.code == 1008
