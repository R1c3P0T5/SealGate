from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.config import get_settings


engine: AsyncEngine | None = None
async_session: async_sessionmaker[AsyncSession] | None = None


async def init_db() -> None:
    """Set up async engine and session factory.

    Deferred to avoid calling get_settings() at import time.
    Production schema is managed by Alembic migrations.
    """

    global engine, async_session

    if engine is not None and async_session is not None:
        return

    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        future=True,
    )
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def create_db_and_tables() -> None:
    """Create all SQLModel tables from metadata.

    For development and testing only — production uses Alembic migrations.
    Safe to call multiple times (create_all is idempotent).
    """

    if engine is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def seed_roles_and_permissions() -> None:
    """Idempotently seed roles and permissions. Safe to call on every startup."""
    from src.permissions.models import Permission, RolePermission
    from src.roles.models import Role

    _ALL_PERMISSIONS: list[tuple[str, str]] = [
        ("face:create", "Create face vectors"),
        ("face:read", "Read face vectors"),
        ("face:delete", "Delete face vectors"),
        ("user:read", "Read any user profile"),
        ("user:update", "Update any user profile"),
        ("user:create", "Create user accounts"),
        ("user:delete", "Delete user accounts"),
        ("user:manage", "Manage user roles and permissions"),
        ("door:create", "Create doors"),
        ("door:open", "Trigger door open"),
        ("door:read", "Read door information"),
        ("door:update", "Update doors"),
        ("door:delete", "Delete doors"),
        ("door:lock", "Lock door"),
        ("door:unlock", "Unlock door"),
        ("door:recognize", "Run door face recognition"),
        ("log:read", "Read access logs"),
        ("log:delete", "Delete access logs"),
    ]
    _ROLE_PERMISSIONS: dict[str, set[str]] = {
        "admin": {p for p, _ in _ALL_PERMISSIONS},
        "user": {"door:open", "door:read", "log:read"},
    }

    async with session_context() as session:
        role_map: dict[str, Role] = {}
        for role_name in ("admin", "user"):
            existing = (
                await session.exec(select(Role).where(Role.name == role_name))
            ).one_or_none()
            if existing is None:
                role = Role(name=role_name)
                session.add(role)
                await session.flush()
                role_map[role_name] = role
            else:
                role_map[role_name] = existing

        perm_map: dict[str, Permission] = {}
        for perm_name, description in _ALL_PERMISSIONS:
            existing_perm = (
                await session.exec(
                    select(Permission).where(Permission.name == perm_name)
                )
            ).one_or_none()
            if existing_perm is None:
                perm = Permission(name=perm_name, description=description)
                session.add(perm)
                await session.flush()
                perm_map[perm_name] = perm
            else:
                perm_map[perm_name] = existing_perm

        for role_name, perm_names in _ROLE_PERMISSIONS.items():
            role = role_map[role_name]
            for perm_name in perm_names:
                perm = perm_map[perm_name]
                exists = (
                    await session.exec(
                        select(RolePermission).where(
                            RolePermission.role_id == role.id,
                            RolePermission.permission_id == perm.id,
                        )
                    )
                ).one_or_none()
                if exists is None:
                    session.add(RolePermission(role_id=role.id, permission_id=perm.id))

        await session.commit()


async def close_db() -> None:
    """Dispose the engine and clear the session factory."""

    global engine, async_session
    if engine is None:
        return
    await engine.dispose()
    engine = None
    async_session = None


@asynccontextmanager
async def session_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager that yields a session; for use outside request handling."""

    if async_session is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")

    async with async_session() as session:
        yield session


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session (FastAPI dependency)."""

    if async_session is None:
        raise RuntimeError("Database is not initialized. Call init_db() first.")

    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
