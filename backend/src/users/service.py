from uuid import UUID

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import UserResponse
from src.core.exceptions import (
    EmailAlreadyInUseError,
    UserNotFoundError,
)
from src.core.utils import utc_now_naive
from src.roles.models import Role
from src.users.models import User
from src.users.schemas import UserUpdateRequest


async def user_response(user: User, session: AsyncSession) -> UserResponse:
    role = await session.get(Role, user.role_id)  # type: ignore[attr-defined]
    if role is None:
        raise RuntimeError("User role seed data is missing.")
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role_name=role.name,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def get_user_by_id(user_id: UUID, session: AsyncSession) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    return user


async def update_user(
    user_id: UUID,
    request: UserUpdateRequest,
    session: AsyncSession,
) -> User:
    user = await get_user_by_id(user_id, session)

    if request.full_name is not None:
        user.full_name = request.full_name
    if request.email is not None:
        user.email = request.email
    user.updated_at = utc_now_naive()

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        if "email" in str(exc).lower():
            raise EmailAlreadyInUseError() from exc
        raise

    return user


async def delete_user(
    user_id: UUID,
    session: AsyncSession,
) -> None:
    user = await get_user_by_id(user_id, session)

    await session.delete(user)
    await session.commit()


async def set_user_active(
    user_id: UUID,
    is_active: bool,
    session: AsyncSession,
) -> User:
    user = await get_user_by_id(user_id, session)

    user.is_active = is_active
    user.updated_at = utc_now_naive()

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


async def list_users(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 10,
) -> tuple[int, list[User]]:
    total = (await session.exec(select(func.count()).select_from(User))).one()
    users = (await session.exec(select(User).offset(skip).limit(limit))).all()

    return total, list(users)
