import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.roles.models import Role
from src.users.models import User


@pytest.mark.asyncio
async def test_client_fixture_exposes_fastapi_app(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_test_user_fixture_persists_regular_user(
    database_session: AsyncSession,
    test_user: User,
    seeded_roles: dict[str, Role],
) -> None:
    persisted_user = await database_session.get(User, test_user.id)

    assert persisted_user is not None
    assert persisted_user.username == "testuser"
    assert persisted_user.role_id == seeded_roles["user"].id
    assert persisted_user.is_active is True
    assert persisted_user.password_hash != "TestPassword123"


@pytest.mark.asyncio
async def test_test_admin_fixture_persists_admin_user(
    database_session: AsyncSession,
    test_admin: User,
    seeded_roles: dict[str, Role],
) -> None:
    persisted_admin = await database_session.get(User, test_admin.id)

    assert persisted_admin is not None
    assert persisted_admin.username == "admin"
    assert persisted_admin.role_id == seeded_roles["admin"].id
    assert persisted_admin.is_active is True


@pytest.mark.asyncio
async def test_database_session_is_isolated(database_session: AsyncSession) -> None:
    result = await database_session.exec(select(User))

    assert result.all() == []
