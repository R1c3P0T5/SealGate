from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.auth.schemas import UserLoginRequest, UserRegisterRequest
from src.auth.utils import (
    create_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from src.core.config import Settings
from src.core.exceptions import (
    EmailAlreadyInUseError,
    InactiveUserError,
    InvalidCredentialsError,
    UsernameAlreadyExistsError,
)
from src.roles.models import Role
from src.users.models import User


async def ensure_default_admin(
    settings: Settings, session: AsyncSession
) -> User | None:
    """Create the configured default admin once, without overwriting existing users."""

    if (
        settings.DEFAULT_ADMIN_USERNAME is None
        or settings.DEFAULT_ADMIN_PASSWORD is None
    ):
        return None

    normalized_username = settings.DEFAULT_ADMIN_USERNAME.lower()

    existing_user = (
        await session.exec(select(User).where(User.username == normalized_username))
    ).one_or_none()
    if existing_user is not None:
        return existing_user

    validate_password_strength(
        settings.DEFAULT_ADMIN_PASSWORD,
        normalized_username,
        settings.DEFAULT_ADMIN_EMAIL,
    )
    admin_role = (
        await session.exec(select(Role).where(Role.name == "admin"))
    ).one_or_none()
    if admin_role is None:
        raise RuntimeError("Admin role seed data is missing.")

    admin = User(
        username=normalized_username,
        email=settings.DEFAULT_ADMIN_EMAIL,
        password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
        full_name=settings.DEFAULT_ADMIN_FULL_NAME or settings.DEFAULT_ADMIN_USERNAME,
        role_id=admin_role.id,
        is_active=True,
    )
    session.add(admin)
    await session.commit()
    return admin


async def register_user(
    request: UserRegisterRequest,
    session: AsyncSession,
) -> User:
    """Register a new user pending admin activation."""

    validate_password_strength(
        request.password, request.username.lower(), request.email
    )
    stmt = select(Role).where(Role.name == "user")
    user_role = (await session.exec(stmt)).one()

    user = User(
        username=request.username.lower(),
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        role_id=user_role.id,
        is_active=False,
    )

    try:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        error = str(exc).lower()
        if "username" in error:
            raise UsernameAlreadyExistsError() from exc
        if "email" in error:
            raise EmailAlreadyInUseError() from exc
        raise

    return user


async def authenticate_user(
    request: UserLoginRequest,
    session: AsyncSession,
) -> tuple[User, str]:
    user = (
        await session.exec(
            select(User).where(User.username == request.username.lower())
        )
    ).one_or_none()

    if user is None:
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InactiveUserError()

    if not verify_password(request.password, user.password_hash):
        raise InvalidCredentialsError()

    return user, create_access_token(user.id)
