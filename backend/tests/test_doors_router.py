from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token, hash_password
from src.access_logs.models import AccessLog
from src.doors.models import Door
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


class _FakeAccessEventBroker:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> None:
        self.events.append(event)


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


@pytest.mark.asyncio
async def test_list_doors_returns_empty_without_auth(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/doors")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 0
    assert "doors" in data


@pytest.mark.asyncio
async def test_get_door_returns_door_without_auth(
    client: AsyncClient,
    database_session: AsyncSession,
) -> None:
    door = await _create_door(database_session)

    response = await client.get(f"/api/doors/{door.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(door.id)


@pytest.mark.asyncio
async def test_get_door_returns_404_for_missing_door(
    client: AsyncClient,
) -> None:
    response = await client.get(f"/api/doors/{uuid4()}")

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
    _, token = await _create_admin_with_token(database_session)
    door = await _create_door(database_session)

    response = await client.delete(f"/api/doors/{door.id}", headers=_auth(token))

    assert response.status_code == 204
    assert response.content == b""


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
