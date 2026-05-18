from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import UserLoginRequest, UserRegisterRequest
from src.auth.utils import decode_token, hash_password
from src.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    UserNotFoundError,
    UsernameAlreadyExistsError,
)
from src.roles.models import Role
from src.users.models import User


@pytest.mark.asyncio
async def test_register_user_hashes_password_and_persists_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import register_user

    username = f"user_{uuid4().hex[:12]}"
    request = UserRegisterRequest(
        username=username,
        password="MySecurePass123",
        full_name="John Doe",
        email=f"{username}@example.com",
    )

    user = await register_user(request, database_session)

    assert user.id is not None
    assert user.username == username
    assert user.password_hash != request.password
    assert user.role_id == seeded_roles["user"].id
    assert user.is_active is True


@pytest.mark.asyncio
async def test_register_user_rejects_duplicate_username(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import register_user

    username = f"dupe_{uuid4().hex[:12]}"
    request = UserRegisterRequest(
        username=username,
        password="MySecurePass123",
        full_name="John Doe",
    )
    await register_user(request, database_session)

    with pytest.raises(UsernameAlreadyExistsError):
        await register_user(request, database_session)


@pytest.mark.asyncio
async def test_authenticate_user_returns_user_and_access_token(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import authenticate_user

    password = "MySecurePass123"
    user = User(
        username=f"login_{uuid4().hex}",
        password_hash=hash_password(password),
        full_name="Login User",
        role_id=seeded_roles["user"].id,
    )
    database_session.add(user)
    await database_session.commit()

    authenticated_user, token = await authenticate_user(
        UserLoginRequest(username=user.username, password=password),
        database_session,
    )

    payload = decode_token(token)

    assert authenticated_user.id == user.id
    assert payload is not None
    assert payload["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_authenticate_user_rejects_bad_password(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import authenticate_user

    user = User(
        username=f"bad_password_{uuid4().hex}",
        password_hash=hash_password("MySecurePass123"),
        full_name="Bad Password",
        role_id=seeded_roles["user"].id,
    )
    database_session.add(user)
    await database_session.commit()

    with pytest.raises(InvalidCredentialsError):
        await authenticate_user(
            UserLoginRequest(username=user.username, password="WrongPassword123"),
            database_session,
        )


@pytest.mark.asyncio
async def test_authenticate_user_rejects_inactive_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> None:
    from src.auth.service import authenticate_user

    password = "MySecurePass123"
    user = User(
        username=f"inactive_login_{uuid4().hex}",
        password_hash=hash_password(password),
        full_name="Inactive Login",
        role_id=seeded_roles["user"].id,
        is_active=False,
    )
    database_session.add(user)
    await database_session.commit()

    with pytest.raises(InactiveUserError):
        await authenticate_user(
            UserLoginRequest(username=user.username, password=password),
            database_session,
        )


@pytest.mark.asyncio
async def test_get_user_by_id_rejects_missing_user(
    database_session: AsyncSession,
) -> None:
    from src.users.service import get_user_by_id

    with pytest.raises(UserNotFoundError):
        await get_user_by_id(uuid4(), database_session)
