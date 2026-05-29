from unittest.mock import MagicMock
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token, hash_password
from src.access_logs.models import AccessLog
from src.devices.models import Device
from src.devices.service import hash_device_token
from src.doors.access import DOOR_DELETE_ACTION, DOOR_UNLOCK_ACTION, DOOR_UPDATE_ACTION
from src.doors.models import Door, UserDoorPermission
from src.faces.service import add_face_vector
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


MOCK_EMBEDDING = np.random.default_rng(42).random(128, dtype=np.float32).tobytes()


class _FakeAccessEventBroker:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _make_jpeg_bytes() -> bytes:
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


async def _grant_role_permission(
    session: AsyncSession, role: Role, permission_name: str
) -> None:
    permission = (
        await session.exec(select(Permission).where(Permission.name == permission_name))
    ).one_or_none()
    if permission is None:
        permission = Permission(name=permission_name)
        session.add(permission)
        await session.flush()

    existing = (
        await session.exec(
            select(RolePermission).where(
                RolePermission.role_id == role.id,
                RolePermission.permission_id == permission.id,
            )
        )
    ).one_or_none()
    if existing is None:
        session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        await session.commit()


async def _create_admin_with_token(session: AsyncSession) -> tuple[User, str]:
    role = (await session.exec(select(Role).where(Role.name == "admin"))).one()
    for permission_name in (
        "door:create",
        "door:update",
        "door:delete",
        "door:unlock",
    ):
        await _grant_role_permission(session, role, permission_name)

    admin = User(
        username=f"admin_{uuid4().hex[:10]}",
        email=f"admin_{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("AdminPass123!"),
        full_name="Admin User",
        role_id=role.id,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    await session.refresh(admin)
    return admin, create_access_token(admin.id)


async def _create_user_with_door_permission(
    session: AsyncSession, seeded_roles: dict[str, Role], permission_name: str
) -> tuple[User, str]:
    role = seeded_roles["user"]
    await _grant_role_permission(session, role, permission_name)

    user = User(
        username=f"door_user_{uuid4().hex[:10]}",
        email=f"door_user_{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("UserPass123!"),
        full_name="Door Permission User",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user.id)


async def _create_door(
    session: AsyncSession,
    *,
    name: str | None = None,
    mqtt_id: str | None = None,
    has_mqtt_id: bool = True,
    is_active: bool = True,
) -> Door:
    _name = name or f"door_{uuid4().hex[:12]}"
    door = Door(
        name=_name,
        mqtt_id=mqtt_id or (_name.lower().replace(" ", "-") if has_mqtt_id else None),
        is_active=is_active,
    )
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _device_auth(token: str) -> dict[str, str]:
    return {"X-Device-Token": token}


async def _create_device(
    session: AsyncSession,
    door: Door,
    token: str = "device-token",
    *,
    active: bool = True,
) -> str:
    session.add(
        Device(
            name=f"device_{uuid4().hex[:12]}",
            door_id=door.id,
            token_hash=hash_device_token(token),
            is_active=active,
        )
    )
    await session.commit()
    return token


def test_doors_router_exposes_expected_routes() -> None:
    from src.doors.router import router

    routes = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in router.routes
        if isinstance(route, APIRoute)
    }

    assert router.prefix == "/api/doors"
    assert ("/api/doors", ("GET",)) in routes
    assert ("/api/doors", ("POST",)) in routes
    assert ("/api/doors/{door_id}", ("GET",)) in routes
    assert ("/api/doors/{door_id}", ("PUT",)) in routes
    assert ("/api/doors/{door_id}", ("DELETE",)) in routes
    assert ("/api/doors/{door_id}/unlock", ("POST",)) in routes
    assert ("/api/doors/{door_id}/recognize", ("POST",)) in routes


@pytest.mark.asyncio
async def test_list_doors_requires_auth(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/doors")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_doors_allows_user_with_door_read(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.get(
        "/api/doors",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 0
    assert "doors" in data


@pytest.mark.asyncio
async def test_get_door_requires_auth(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    response = await client.get(f"/api/doors/{door.id}")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_door_allows_user_with_door_read(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    door = await _create_door(database_session)

    response = await client.get(
        f"/api/doors/{door.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(door.id)


@pytest.mark.asyncio
async def test_get_door_returns_404_for_missing_door(
    client: AsyncClient,
    test_user: User,
) -> None:
    response = await client.get(
        f"/api/doors/{uuid4()}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Door not found"


@pytest.mark.asyncio
async def test_create_door_requires_admin(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/doors", json={"name": "Locked Out"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_door_as_admin_returns_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)

    response = await client.post(
        "/api/doors",
        json={"name": "Server Room", "mqtt_id": "server-room", "location": "Floor 3"},
        headers=_auth(token),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Server Room"
    assert data["mqtt_id"] == "server-room"
    assert data["location"] == "Floor 3"
    assert data["is_active"] is True
    assert data["id"]


@pytest.mark.asyncio
async def test_create_door_allows_user_with_create_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_user_with_door_permission(
        database_session, seeded_roles, "door:create"
    )

    response = await client.post(
        "/api/doors",
        json={"name": "Permission Door", "mqtt_id": "permission-door"},
        headers=_auth(token),
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Permission Door"


@pytest.mark.asyncio
async def test_create_door_rejects_duplicate_name(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    await _create_door(database_session, name="Unique Door", mqtt_id="unique-door")

    response = await client.post(
        "/api/doors",
        json={"name": "Unique Door", "mqtt_id": "other-id"},
        headers=_auth(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Door name already in use"


@pytest.mark.asyncio
async def test_create_door_rejects_duplicate_mqtt_id(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    await _create_door(database_session, name="First Door", mqtt_id="shared-id")

    response = await client.post(
        "/api/doors",
        json={"name": "Second Door", "mqtt_id": "shared-id"},
        headers=_auth(token),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Door MQTT ID already in use"


@pytest.mark.asyncio
async def test_update_door_as_admin_applies_change(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session, name="Before Update")

    response = await client.put(
        f"/api/doors/{door.id}",
        json={"is_active": False},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_update_door_requires_admin(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    response = await client.put(f"/api/doors/{door.id}", json={"name": "No Auth"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_door_as_admin_returns_204(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)
    database_session.add(
        UserDoorPermission(
            user_id=user.id,
            door_id=door.id,
            action=DOOR_UNLOCK_ACTION,
        )
    )
    await database_session.commit()

    response = await client.delete(f"/api/doors/{door.id}", headers=_auth(token))

    permission = await database_session.get(
        UserDoorPermission, (user.id, door.id, DOOR_UNLOCK_ACTION)
    )
    assert response.status_code == 204
    assert response.content == b""
    assert permission is None


@pytest.mark.asyncio
async def test_delete_door_requires_admin(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    response = await client.delete(f"/api/doors/{door.id}")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_nonexistent_door_returns_404(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)

    response = await client.delete(f"/api/doors/{uuid4()}", headers=_auth(token))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unlock_door_requires_auth(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)

    response = await client.post(f"/api/doors/{door.id}/unlock")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unlock_door_rejects_user_without_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    user = User(
        username=f"no_unlock_{uuid4().hex[:10]}",
        email=f"no_unlock_{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("UserPass123!"),
        full_name="No Unlock User",
        role_id=seeded_roles["user"].id,
        is_active=True,
    )
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)
    door = await _create_door(database_session)

    response = await client.post(
        f"/api/doors/{door.id}/unlock",
        headers=_auth(create_access_token(user.id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unlock_door_returns_404_for_missing_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)

    response = await client.post(f"/api/doors/{uuid4()}/unlock", headers=_auth(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Door not found"


@pytest.mark.asyncio
async def test_unlock_door_rejects_inactive_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session, is_active=False)

    response = await client.post(f"/api/doors/{door.id}/unlock", headers=_auth(token))

    assert response.status_code == 409
    assert response.json()["detail"] == "Door is inactive"


@pytest.mark.asyncio
async def test_unlock_door_mqtt_failure_returns_502_without_access_log(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from src.doors.mqtt import DoorUnlockPublishError
    import src.doors.router as router

    async def fail_publish(_door: Door) -> None:
        raise DoorUnlockPublishError("offline")

    monkeypatch.setattr(router, "publish_door_unlock", fail_publish)
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)

    response = await client.post(f"/api/doors/{door.id}/unlock", headers=_auth(token))

    logs = (
        await database_session.exec(
            select(AccessLog).where(AccessLog.door_id == door.id)
        )
    ).all()
    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to publish door unlock command"
    assert list(logs) == []


@pytest.mark.asyncio
async def test_unlock_door_without_mqtt_id_returns_502_without_access_log(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session, has_mqtt_id=False)

    response = await client.post(f"/api/doors/{door.id}/unlock", headers=_auth(token))

    logs = (
        await database_session.exec(
            select(AccessLog).where(AccessLog.door_id == door.id)
        )
    ).all()
    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to publish door unlock command"
    assert list(logs) == []


@pytest.mark.asyncio
async def test_unlock_door_success_writes_access_log_and_broadcasts_event(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    import src.doors.router as router

    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    broker = _FakeAccessEventBroker()
    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(app.state, "access_event_broker", broker)
    user, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)

    response = await client.post(f"/api/doors/{door.id}/unlock", headers=_auth(token))

    logs = list(
        (
            await database_session.exec(
                select(AccessLog).where(AccessLog.door_id == door.id)
            )
        ).all()
    )
    assert response.status_code == 200
    data = response.json()
    assert data == {
        "door_id": str(door.id),
        "user_id": str(user.id),
        "username": user.username,
        "confidence": None,
        "door_opened": True,
        "access_log_id": str(logs[0].id),
    }
    assert published_doors == [door]
    assert len(logs) == 1
    assert logs[0].user_id == user.id
    assert logs[0].username == user.username
    assert logs[0].confidence is None
    assert logs[0].door_opened is True
    assert len(broker.events) == 1
    assert broker.events[0].id == logs[0].id


@pytest.mark.asyncio
async def test_unlock_door_returns_success_when_access_log_write_fails(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    seeded_roles: dict[str, Role],
) -> None:
    import src.doors.router as router

    async def fake_publish(_door: Door) -> None:
        return None

    async def fail_create_access_log(*_args, **_kwargs) -> None:
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(router, "create_access_log", fail_create_access_log)
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)

    response = await client.post(f"/api/doors/{door.id}/unlock", headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["access_log_id"] is None
    assert "Failed to write access log for manual door unlock" in caplog.text


@pytest.mark.asyncio
async def test_recognize_door_requires_auth(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing device token"


@pytest.mark.asyncio
async def test_recognize_door_rejects_jwt_auth(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_auth(token),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing device token"


@pytest.mark.asyncio
async def test_recognize_door_rejects_wrong_device_token(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)
    await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth("wrong-token"),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid device token"


@pytest.mark.asyncio
async def test_recognize_door_rejects_wrong_device_door(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    configured_door = await _create_door(database_session)
    other_door = await _create_door(database_session)
    token = await _create_device(database_session, configured_door)

    response = await client.post(
        f"/api/doors/{other_door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid device token"


@pytest.mark.asyncio
async def test_recognize_door_returns_403_for_unconfigured_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    configured_door = await _create_door(database_session)
    token = await _create_device(database_session, configured_door)

    response = await client.post(
        f"/api/doors/{uuid4()}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recognize_door_rejects_inactive_door_without_recognition(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.faces.engine import get_engine

    engine = MagicMock()
    app.dependency_overrides[get_engine] = lambda: engine
    door = await _create_door(database_session, is_active=False)
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Door is inactive"
    engine.detect_and_embed.assert_not_called()


@pytest.mark.asyncio
async def test_recognize_door_no_face_returns_400_without_access_log(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    logs = (
        await database_session.exec(
            select(AccessLog).where(AccessLog.door_id == door.id)
        )
    ).all()
    assert response.status_code == 400
    assert response.json()["detail"] == "No face detected in the provided image"
    assert list(logs) == []


@pytest.mark.asyncio
async def test_recognize_door_unmatched_does_not_open_or_write_access_log(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    door = await _create_door(database_session)
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    logs = (
        await database_session.exec(
            select(AccessLog).where(AccessLog.door_id == door.id)
        )
    ).all()
    assert response.status_code == 200
    assert response.json() == {
        "matched": False,
        "user_id": None,
        "username": None,
        "confidence": 0.0,
        "door_opened": False,
        "access_log_id": None,
    }
    assert published_doors == []
    assert list(logs) == []


@pytest.mark.asyncio
async def test_recognize_door_matched_without_door_access_does_not_open(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    broker = _FakeAccessEventBroker()
    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(app.state, "access_event_broker", broker)
    user, _token = await _create_user_with_door_permission(
        database_session, seeded_roles, "door:read"
    )
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = await _create_door(database_session)
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    logs = list(
        (
            await database_session.exec(
                select(AccessLog).where(AccessLog.door_id == door.id)
            )
        ).all()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["user_id"] == str(user.id)
    assert data["door_opened"] is False
    assert data["access_log_id"] == str(logs[0].id)
    assert published_doors == []
    assert len(logs) == 1
    assert logs[0].user_id == user.id
    assert logs[0].door_opened is False
    assert len(broker.events) == 1
    assert broker.events[0].id == logs[0].id


@pytest.mark.asyncio
async def test_recognize_door_matched_inactive_user_does_not_open(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    broker = _FakeAccessEventBroker()
    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(app.state, "access_event_broker", broker)
    user, _token = await _create_user_with_door_permission(
        database_session, seeded_roles, "door:read"
    )
    user.is_active = False
    database_session.add(user)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = await _create_door(database_session)
    database_session.add(
        UserDoorPermission(
            user_id=user.id,
            door_id=door.id,
            action=DOOR_UNLOCK_ACTION,
        )
    )
    await database_session.commit()
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    logs = list(
        (
            await database_session.exec(
                select(AccessLog).where(AccessLog.door_id == door.id)
            )
        ).all()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["user_id"] == str(user.id)
    assert data["door_opened"] is False
    assert data["access_log_id"] == str(logs[0].id)
    assert published_doors == []
    assert len(logs) == 1
    assert logs[0].door_opened is False
    assert len(broker.events) == 1


@pytest.mark.asyncio
async def test_recognize_door_matched_publish_success_writes_access_log(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    broker = _FakeAccessEventBroker()
    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(app.state, "access_event_broker", broker)
    user, _token = await _create_admin_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = await _create_door(database_session)
    database_session.add(
        UserDoorPermission(
            user_id=user.id,
            door_id=door.id,
            action=DOOR_UNLOCK_ACTION,
        )
    )
    await database_session.commit()
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    logs = list(
        (
            await database_session.exec(
                select(AccessLog).where(AccessLog.door_id == door.id)
            )
        ).all()
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["user_id"] == str(user.id)
    assert data["username"] == user.username
    assert data["confidence"] == pytest.approx(1.0, abs=1e-5)
    assert data["door_opened"] is True
    assert data["access_log_id"] == str(logs[0].id)
    assert published_doors == [door]
    assert len(logs) == 1
    assert logs[0].user_id == user.id
    assert logs[0].username == user.username
    assert logs[0].confidence == pytest.approx(1.0, abs=1e-5)
    assert logs[0].door_opened is True
    assert len(broker.events) == 1
    assert broker.events[0].id == logs[0].id


@pytest.mark.asyncio
async def test_recognize_door_matched_publish_failure_writes_failed_open_log(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.doors.mqtt import DoorUnlockPublishError
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING

    async def fail_publish(_door: Door) -> None:
        raise DoorUnlockPublishError("offline")

    broker = _FakeAccessEventBroker()
    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fail_publish)
    monkeypatch.setattr(app.state, "access_event_broker", broker)
    user, _token = await _create_admin_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = await _create_door(database_session)
    database_session.add(
        UserDoorPermission(
            user_id=user.id,
            door_id=door.id,
            action=DOOR_UNLOCK_ACTION,
        )
    )
    await database_session.commit()
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to publish door unlock command"


@pytest.mark.asyncio
async def test_recognize_door_matched_publish_and_log_failure_returns_500(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    from main import app
    from src.doors.mqtt import DoorUnlockPublishError
    from src.faces.engine import get_engine
    import src.doors.router as router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING

    async def fail_publish(_door: Door) -> None:
        raise DoorUnlockPublishError("offline")

    async def fail_create_access_log(*_args, **_kwargs) -> None:
        raise RuntimeError("db down")

    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(router, "publish_door_unlock", fail_publish)
    monkeypatch.setattr(router, "create_access_log", fail_create_access_log)
    user, _token = await _create_admin_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = await _create_door(database_session)
    database_session.add(
        UserDoorPermission(
            user_id=user.id,
            door_id=door.id,
            action=DOOR_UNLOCK_ACTION,
        )
    )
    await database_session.commit()
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Failed to publish door unlock command"


async def _create_user_with_per_door_permission(
    session: AsyncSession,
    seeded_roles: dict[str, Role],
    door: Door,
    action: str,
) -> tuple[User, str]:
    """Create a user with only per-door ACL entry — no extra RBAC permissions."""
    role = seeded_roles["user"]
    user = User(
        username=f"pdoor_{uuid4().hex[:10]}",
        email=f"pdoor_{uuid4().hex[:10]}@example.com",
        password_hash=hash_password("UserPass123!"),
        full_name="Per Door User",
        role_id=role.id,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(UserDoorPermission(user_id=user.id, door_id=door.id, action=action))
    await session.commit()
    await session.refresh(user)
    return user, create_access_token(user.id)


@pytest.mark.asyncio
async def test_update_door_allows_user_with_per_door_update_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, door, DOOR_UPDATE_ACTION
    )

    response = await client.put(
        f"/api/doors/{door.id}",
        json={"location": "Updated Location"},
        headers=_auth(token),
    )

    assert response.status_code == 200
    assert response.json()["location"] == "Updated Location"


@pytest.mark.asyncio
async def test_update_door_denies_user_with_update_permission_on_different_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    other_door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, other_door, DOOR_UPDATE_ACTION
    )

    response = await client.put(
        f"/api/doors/{door.id}",
        json={"location": "Should Fail"},
        headers=_auth(token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_door_allows_user_with_per_door_delete_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, door, DOOR_DELETE_ACTION
    )

    response = await client.delete(f"/api/doors/{door.id}", headers=_auth(token))

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_door_denies_user_with_delete_permission_on_different_door(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    other_door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, other_door, DOOR_DELETE_ACTION
    )

    response = await client.delete(f"/api/doors/{door.id}", headers=_auth(token))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_per_door_update_permission_inactive_user_denied(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    door = await _create_door(database_session)
    user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, door, DOOR_UPDATE_ACTION
    )
    user.is_active = False
    database_session.add(user)
    await database_session.commit()

    response = await client.put(
        f"/api/doors/{door.id}",
        json={"location": "Should Fail"},
        headers=_auth(token),
    )

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_per_door_update_permission_does_not_grant_delete(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    """update ACL on a door must not allow delete on the same door."""
    door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, door, DOOR_UPDATE_ACTION
    )

    response = await client.delete(f"/api/doors/{door.id}", headers=_auth(token))

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_per_door_delete_permission_does_not_grant_update(
    client: AsyncClient,
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    """delete ACL on a door must not allow update on the same door."""
    door = await _create_door(database_session)
    _user, token = await _create_user_with_per_door_permission(
        database_session, seeded_roles, door, DOOR_DELETE_ACTION
    )

    response = await client.put(
        f"/api/doors/{door.id}",
        json={"location": "Cross-action escalation"},
        headers=_auth(token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recognize_both_mode_face_ok_does_not_unlock_alone(
    client: AsyncClient,
    database_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    seeded_roles: dict[str, Role],
) -> None:
    """In both mode, face match alone must not open the door."""
    from main import app
    from src.faces.engine import get_engine
    from src.handsign.session import DoorSessionStore
    import src.doors.router as doors_router

    engine = MagicMock()
    engine.detect_and_embed.return_value = MOCK_EMBEDDING
    published_doors: list[Door] = []

    async def fake_publish(door: Door) -> None:
        published_doors.append(door)

    store = DoorSessionStore()
    app.dependency_overrides[get_engine] = lambda: engine
    monkeypatch.setattr(doors_router, "publish_door_unlock", fake_publish)
    monkeypatch.setattr(doors_router, "get_session_store", lambda: store)

    user, _token = await _create_admin_with_token(database_session)
    await add_face_vector(user.id, MOCK_EMBEDDING, database_session)
    door = Door(
        name=f"both_{uuid4().hex[:8]}",
        mqtt_id=f"both_{uuid4().hex[:8]}",
        auth_mode="both",
    )
    database_session.add(door)
    await database_session.commit()
    await database_session.refresh(door)
    database_session.add(
        UserDoorPermission(user_id=user.id, door_id=door.id, action=DOOR_UNLOCK_ACTION)
    )
    await database_session.commit()
    token = await _create_device(database_session, door)

    response = await client.post(
        f"/api/doors/{door.id}/recognize",
        files={"image": ("frame.jpg", _make_jpeg_bytes(), "image/jpeg")},
        headers=_device_auth(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["matched"] is True
    assert data["door_opened"] is False
    assert not published_doors
    door_session = store.get_or_create(door.id)
    assert door_session.face_ok is True
