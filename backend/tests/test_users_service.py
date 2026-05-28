from uuid import UUID, uuid4

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.exceptions import (
    EmailAlreadyInUseError,
    UserNotFoundError,
)
from src.roles.models import Role
from src.users.models import User
from src.users.schemas import UserUpdateRequest


async def create_user(
    session: AsyncSession,
    *,
    username: str | None = None,
    email: str | None = None,
    role_name: str = "user",
) -> User:
    role = (await session.exec(select(Role).where(Role.name == role_name))).one()
    user = User(
        username=username or f"user_{uuid4().hex[:12]}",
        email=email,
        password_hash="hash",
        full_name="Original Name",
        role_id=role.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_get_user_by_id_returns_existing_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import get_user_by_id

    user = await create_user(database_session)

    result = await get_user_by_id(user.id, database_session)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_update_user_allows_self_and_updates_timestamp(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import update_user

    user = await create_user(database_session)
    original_updated_at = user.updated_at

    result = await update_user(
        user.id,
        UserUpdateRequest(full_name="Updated Name"),
        database_session,
    )

    assert result.full_name == "Updated Name"
    assert result.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_update_user_updates_requested_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import update_user

    user = await create_user(database_session)

    result = await update_user(
        user.id,
        UserUpdateRequest(
            full_name=None,
            email=f"{uuid4().hex[:12]}@example.com",
        ),
        database_session,
    )

    assert result.id == user.id
    assert result.email is not None


@pytest.mark.asyncio
@pytest.mark.asyncio
async def test_update_user_rejects_duplicate_email(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import update_user

    email = f"{uuid4().hex[:12]}@example.com"
    await create_user(database_session, email=email)
    user = await create_user(database_session)

    with pytest.raises(EmailAlreadyInUseError):
        await update_user(
            user.id,
            UserUpdateRequest(full_name=None, email=email),
            database_session,
        )


@pytest.mark.asyncio
async def test_delete_user_deletes_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import delete_user, get_user_by_id

    user = await create_user(database_session)

    assert await delete_user(user.id, database_session) is None

    with pytest.raises(UserNotFoundError):
        await get_user_by_id(user.id, database_session)


@pytest.mark.asyncio
async def test_set_user_active_toggles_flag_and_bumps_timestamp(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import set_user_active

    user = await create_user(database_session)
    user.is_active = False
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)
    original_updated_at = user.updated_at

    result = await set_user_active(user.id, True, database_session)

    assert result.is_active is True
    assert result.updated_at > original_updated_at

    deactivated = await set_user_active(result.id, False, database_session)
    assert deactivated.is_active is False


@pytest.mark.asyncio
async def test_set_user_active_raises_when_user_missing(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import set_user_active

    with pytest.raises(UserNotFoundError):
        await set_user_active(uuid4(), True, database_session)


@pytest.mark.asyncio
async def test_list_users_returns_total_and_paginated_users(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.users.service import list_users

    created_ids: set[UUID] = set()
    for _ in range(3):
        user = await create_user(database_session)
        created_ids.add(user.id)

    total, users = await list_users(database_session, skip=0, limit=100)

    assert total >= 3
    assert created_ids.issubset({user.id for user in users})
