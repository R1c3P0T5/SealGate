from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
from src.doors.models import Door
from src.handsign.models import DoorJutsu, Jutsu
from src.permissions.models import Permission, RolePermission
from src.roles.models import Role
from src.users.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


async def _grant_admin_permissions(
    session: AsyncSession, admin: User, permission_names: tuple[str, ...]
) -> None:
    role = await session.get(Role, admin.role_id)
    assert role is not None
    for permission_name in permission_names:
        await _grant_role_permission(session, role, permission_name)


async def _create_jutsu(
    session: AsyncSession,
    *,
    name: str | None = None,
    signs: list[str] | None = None,
) -> Jutsu:
    jutsu = Jutsu(
        name=name or f"jutsu_{uuid4().hex[:12]}",
        signs=signs or ["ne", "tora"],
    )
    session.add(jutsu)
    await session.commit()
    await session.refresh(jutsu)
    return jutsu


async def _create_door(session: AsyncSession) -> Door:
    name = f"door_{uuid4().hex[:12]}"
    door = Door(name=name, mqtt_id=name, is_active=True)
    session.add(door)
    await session.commit()
    await session.refresh(door)
    return door


@pytest.mark.asyncio
async def test_create_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:create",))

    response = await client.post(
        "/api/jutsu",
        json={"name": "Shadow Clone", "signs": ["tora", "mi"]},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Shadow Clone"
    assert data["signs"] == ["tora", "mi"]


@pytest.mark.asyncio
async def test_get_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:read",))
    jutsu = await _create_jutsu(database_session, signs=["ne", "ushi", "tora"])

    response = await client.get(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    assert response.json()["signs"] == ["ne", "ushi", "tora"]


@pytest.mark.asyncio
async def test_list_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:read",))
    await _create_jutsu(database_session)

    response = await client.get(
        "/api/jutsu",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert "jutsu" in data


@pytest.mark.asyncio
async def test_update_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:update",))
    jutsu = await _create_jutsu(database_session)

    response = await client.put(
        f"/api/jutsu/{jutsu.id}",
        json={"name": "Updated Jutsu"},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated Jutsu"


@pytest.mark.asyncio
async def test_delete_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:delete",))
    jutsu = await _create_jutsu(database_session)

    response = await client.delete(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_assign_jutsu_to_door(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("door:update",))
    door = await _create_door(database_session)
    jutsu = await _create_jutsu(database_session)

    response = await client.post(
        f"/api/doors/{door.id}/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_unassign_jutsu_from_door(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("door:update",))
    door = await _create_door(database_session)
    jutsu = await _create_jutsu(database_session)
    database_session.add(DoorJutsu(door_id=door.id, jutsu_id=jutsu.id))
    await database_session.commit()

    response = await client.delete(
        f"/api/doors/{door.id}/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_create_jutsu_invalid_sign(
    client: AsyncClient,
    database_session: AsyncSession,
    test_admin: User,
) -> None:
    await _grant_admin_permissions(database_session, test_admin, ("jutsu:create",))

    response = await client.post(
        "/api/jutsu",
        json={"name": "Invalid Jutsu", "signs": ["invalid_sign"]},
        headers=_auth(create_access_token(test_admin.id)),
    )

    assert response.status_code == 422
