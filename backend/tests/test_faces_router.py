from collections.abc import AsyncGenerator
from unittest.mock import MagicMock
from uuid import uuid4

import cv2
import numpy as np
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token, hash_password
from src.core.database import get_session
from src.faces.engine import get_engine
from src.faces.service import add_face_vector
from src.roles.models import Role
from src.users.models import User

MOCK_EMBEDDING = np.random.default_rng(42).random(128, dtype=np.float32).tobytes()


def _make_jpeg_bytes() -> bytes:
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


async def _create_user_with_token(
    session: AsyncSession,
    *,
    role_name: str = "user",
) -> tuple[User, str]:
    role = (await session.exec(select(Role).where(Role.name == role_name))).one()
    user = User(
        username=f"user_{uuid4().hex[:12]}",
        email=f"{uuid4().hex[:12]}@example.com",
        password_hash=hash_password("Pass123!"),
        full_name="Face Router User",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user.id)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


@pytest.mark.asyncio
async def test_list_faces_empty_returns_total_and_faces(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
) -> None:
    user, _ = await _create_user_with_token(database_session)

    response = await client.get(f"/api/users/{user.id}/faces")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_faces_forbids_other_user(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
) -> None:
    user, _ = await _create_user_with_token(database_session)
    _, admin_token = await _create_user_with_token(
        database_session,
        role_name="admin",
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
    seeded_roles: dict[str, Role],
) -> None:
    user, token = await _create_user_with_token(database_session)
    face = await add_face_vector(user.id, MOCK_EMBEDDING, database_session)

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
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
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
    seeded_roles: dict[str, Role],
) -> None:
    user, _ = await _create_user_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)

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
    seeded_roles: dict[str, Role],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.faces.router as router

    user, _ = await _create_user_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
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
