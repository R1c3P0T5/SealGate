"""Per-jutsu ACL tests.

Verifies that UserJutsuPermission grants access to specific jutsu
when the user lacks global jutsu:* RBAC permissions.
"""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
from src.handsign.models import Jutsu, UserJutsuPermission
from src.users.models import User


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


async def _grant_jutsu_acl(
    session: AsyncSession, user: User, jutsu: Jutsu, action: str
) -> None:
    session.add(UserJutsuPermission(user_id=user.id, jutsu_id=jutsu.id, action=action))
    await session.commit()


# ---------------------------------------------------------------------------
# GET /api/jutsu/{jutsu_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_jutsu_with_per_resource_read_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """Per-jutsu read ACL grants access to that specific jutsu."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "read")

    response = await client.get(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(jutsu.id)


@pytest.mark.asyncio
async def test_get_jutsu_acl_does_not_grant_access_to_other_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """A per-jutsu ACL for jutsu A does not grant access to jutsu B."""
    jutsu_a = await _create_jutsu(database_session)
    jutsu_b = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu_a, "read")

    response = await client.get(
        f"/api/jutsu/{jutsu_b.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_jutsu_update_acl_does_not_grant_read(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """An update ACL does not imply read access."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "update")

    response = await client.get(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/jutsu/{jutsu_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_jutsu_with_per_resource_update_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """Per-jutsu update ACL allows PUT."""
    jutsu = await _create_jutsu(database_session, name="original")
    await _grant_jutsu_acl(database_session, test_user, jutsu, "update")

    response = await client.put(
        f"/api/jutsu/{jutsu.id}",
        json={"name": "updated"},
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "updated"


@pytest.mark.asyncio
async def test_update_jutsu_acl_does_not_grant_access_to_other_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """Update ACL for jutsu A cannot be used to update jutsu B."""
    jutsu_a = await _create_jutsu(database_session)
    jutsu_b = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu_a, "update")

    response = await client.put(
        f"/api/jutsu/{jutsu_b.id}",
        json={"name": "hacked"},
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_jutsu_read_acl_does_not_grant_update(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """A read ACL does not allow PUT."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "read")

    response = await client.put(
        f"/api/jutsu/{jutsu.id}",
        json={"name": "should-fail"},
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/jutsu/{jutsu_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_jutsu_with_per_resource_delete_permission(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """Per-jutsu delete ACL allows DELETE."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "delete")

    response = await client.delete(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_jutsu_acl_does_not_grant_access_to_other_jutsu(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """Delete ACL for jutsu A cannot be used to delete jutsu B."""
    jutsu_a = await _create_jutsu(database_session)
    jutsu_b = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu_a, "delete")

    response = await client.delete(
        f"/api/jutsu/{jutsu_b.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_jutsu_read_acl_does_not_grant_delete(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
) -> None:
    """A read ACL does not allow DELETE."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "read")

    response = await client.delete(
        f"/api/jutsu/{jutsu.id}",
        headers=_auth(create_access_token(test_user.id)),
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET+PUT /api/users/{user_id}/jutsu  (admin management endpoint)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_user_jutsu_access_grants_read(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
    test_admin: User,
) -> None:
    """PUT /users/{id}/jutsu with action=read creates the ACL entries."""
    jutsu_a = await _create_jutsu(database_session)
    jutsu_b = await _create_jutsu(database_session)

    admin_token = create_access_token(test_admin.id)
    user_token = create_access_token(test_user.id)

    response = await client.put(
        f"/api/users/{test_user.id}/jutsu",
        json={"jutsu_ids": [str(jutsu_a.id), str(jutsu_b.id)]},
        headers=_auth(admin_token),
        params={"action": "read"},
    )
    assert response.status_code == 200
    data = response.json()
    assert set(data["jutsu_ids"]) == {str(jutsu_a.id), str(jutsu_b.id)}

    response = await client.get(
        f"/api/jutsu/{jutsu_a.id}",
        headers=_auth(user_token),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_user_jutsu_access_returns_acl_entries(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
    test_admin: User,
) -> None:
    """GET /users/{id}/jutsu returns current ACL list."""
    jutsu = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu, "read")

    response = await client.get(
        f"/api/users/{test_user.id}/jutsu",
        headers=_auth(create_access_token(test_admin.id)),
        params={"action": "read"},
    )

    assert response.status_code == 200
    assert str(jutsu.id) in response.json()["jutsu_ids"]


@pytest.mark.asyncio
async def test_set_user_jutsu_access_replaces_previous_entries(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
    test_admin: User,
) -> None:
    """PUT /users/{id}/jutsu replaces (not appends) existing entries."""
    jutsu_old = await _create_jutsu(database_session)
    jutsu_new = await _create_jutsu(database_session)
    await _grant_jutsu_acl(database_session, test_user, jutsu_old, "read")

    admin_token = create_access_token(test_admin.id)

    await client.put(
        f"/api/users/{test_user.id}/jutsu",
        json={"jutsu_ids": [str(jutsu_new.id)]},
        headers=_auth(admin_token),
        params={"action": "read"},
    )

    response = await client.get(
        f"/api/users/{test_user.id}/jutsu",
        headers=_auth(admin_token),
        params={"action": "read"},
    )
    assert response.status_code == 200
    ids = response.json()["jutsu_ids"]
    assert str(jutsu_new.id) in ids
    assert str(jutsu_old.id) not in ids


@pytest.mark.asyncio
async def test_set_user_jutsu_access_nonexistent_jutsu_returns_404(
    client: AsyncClient,
    database_session: AsyncSession,
    test_user: User,
    test_admin: User,
) -> None:
    """PUT /users/{id}/jutsu with unknown jutsu_id returns 404."""
    response = await client.put(
        f"/api/users/{test_user.id}/jutsu",
        json={"jutsu_ids": [str(uuid4())]},
        headers=_auth(create_access_token(test_admin.id)),
        params={"action": "read"},
    )

    assert response.status_code == 404
