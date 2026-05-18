from collections.abc import AsyncGenerator
from typing import Any, cast
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.utils import create_access_token
import src.core.database as db
from src.core.exceptions import (
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
)
from src.roles.models import Role
from src.users.models import User


@pytest_asyncio.fixture
async def database_session() -> AsyncGenerator[AsyncSession, None]:
    await db.init_db()
    await db.create_db_and_tables()

    assert db.async_session is not None
    async with db.async_session() as session:
        try:
            yield session
        finally:
            await db.close_db()


def test_oauth2_scheme_uses_auth_login_token_url() -> None:
    from src.auth.dependencies import oauth2_scheme

    model = cast(Any, oauth2_scheme.model)

    assert model.flows.password is not None
    assert model.flows.password.tokenUrl == "/api/auth/token"


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user_from_valid_token(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.dependencies import get_current_user

    user = User(
        username=f"user_{uuid4().hex}",
        password_hash="hash",
        full_name="John Doe",
        role_id=seeded_roles["user"].id,
    )
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)

    token = create_access_token(user.id)

    current_user = await get_current_user(token, database_session)

    assert current_user.id == user.id
    assert current_user.username == user.username


@pytest.mark.asyncio
async def test_get_current_user_rejects_invalid_token(
    database_session: AsyncSession,
) -> None:
    from src.auth.dependencies import get_current_user

    with pytest.raises(InvalidTokenError):
        await get_current_user("invalid.token.here", database_session)


@pytest.mark.asyncio
async def test_get_current_user_rejects_inactive_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.dependencies import get_current_user

    user = User(
        username=f"inactive_{uuid4().hex}",
        password_hash="hash",
        full_name="Inactive User",
        role_id=seeded_roles["user"].id,
        is_active=False,
    )
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)

    token = create_access_token(user.id)

    with pytest.raises(InactiveUserError):
        await get_current_user(token, database_session)


@pytest.mark.asyncio
async def test_get_admin_user_requires_admin_role(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.dependencies import get_admin_user

    admin = User(
        username="admin",
        password_hash="hash",
        full_name="Admin User",
        role_id=seeded_roles["admin"].id,
    )
    user = User(
        username="regular",
        password_hash="hash",
        full_name="Regular User",
        role_id=seeded_roles["user"].id,
    )

    assert await get_admin_user(admin, database_session) is admin

    with pytest.raises(PermissionDeniedError):
        await get_admin_user(user, database_session)
