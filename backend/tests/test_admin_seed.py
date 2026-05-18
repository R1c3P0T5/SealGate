import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import Settings
from src.roles.models import Role
from src.users.models import User


@pytest.mark.asyncio
async def test_ensure_default_admin_skips_when_not_configured(
    database_session: AsyncSession,
) -> None:
    from src.auth.service import ensure_default_admin

    await ensure_default_admin(
        Settings(SECRET_KEY="a" * 32, _env_file=None),  # type: ignore[call-arg]
        database_session,
    )

    users = (await database_session.exec(select(User))).all()
    assert users == []


@pytest.mark.asyncio
async def test_ensure_default_admin_creates_admin_from_settings(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import ensure_default_admin

    await ensure_default_admin(
        Settings(
            SECRET_KEY="b" * 32,
            DEFAULT_ADMIN_USERNAME="admin",
            DEFAULT_ADMIN_PASSWORD="AdminPassword123",
            DEFAULT_ADMIN_EMAIL="admin@example.com",
        ),
        database_session,
    )

    admin = (
        await database_session.exec(select(User).where(User.username == "admin"))
    ).one()
    assert admin.role_id == seeded_roles["admin"].id
    assert admin.is_active is True
    assert admin.full_name == "admin"
    assert admin.email == "admin@example.com"
    assert admin.password_hash != "AdminPassword123"


@pytest.mark.asyncio
async def test_ensure_default_admin_keeps_existing_user_unchanged(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import ensure_default_admin

    existing_user = User(
        username="admin",
        email="existing@example.com",
        password_hash="existing-hash",
        full_name="Existing Admin",
        role_id=seeded_roles["admin"].id,
        is_active=True,
    )
    database_session.add(existing_user)
    await database_session.commit()

    await ensure_default_admin(
        Settings(
            SECRET_KEY="c" * 32,
            DEFAULT_ADMIN_USERNAME="admin",
            DEFAULT_ADMIN_PASSWORD="NewAdminPassword123",
            DEFAULT_ADMIN_FULL_NAME="New Admin",
            DEFAULT_ADMIN_EMAIL="new@example.com",
        ),
        database_session,
    )

    admin = (
        await database_session.exec(select(User).where(User.username == "admin"))
    ).one()
    assert admin.email == "existing@example.com"
    assert admin.password_hash == "existing-hash"
    assert admin.full_name == "Existing Admin"
