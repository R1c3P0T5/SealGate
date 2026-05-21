from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from main import app
from src.auth.utils import hash_password
from src.access_logs.models import AccessLog as _AccessLog  # noqa: F401
from src.core.config import get_settings
from src.core.database import get_session
from src.faces.models import FaceVector as _FaceVector  # noqa: F401
from src.doors.models import Door as _Door  # noqa: F401
from src.permissions.models import (  # noqa: F401
    Permission,
    RolePermission,
    UserPermissionOverride,
)
from src.roles.models import Role
from src.users.models import User


@pytest.fixture(autouse=True)
def isolate_test_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[None, None, None]:
    test_database_url = f"sqlite+aiosqlite:///{tmp_path}/test_jetson_facelock.db"
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def database_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(
        engine,
        expire_on_commit=False,
        autoflush=False,
    ) as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(
    database_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield database_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as async_client:
        yield async_client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_roles(database_session: AsyncSession) -> dict[str, Role]:
    admin_role = Role(name="admin")
    user_role = Role(name="user")
    database_session.add(admin_role)
    database_session.add(user_role)
    await database_session.flush()

    permission_names = [
        "user:read",
        "user:update",
        "user:create",
        "user:delete",
        "user:manage",
        "door:read",
        "door:unlock",
        "camera:preview",
        "log:read",
        "face:create",
        "face:read",
        "face:delete",
    ]
    permissions = [Permission(name=name) for name in permission_names]
    database_session.add_all(permissions)
    await database_session.flush()
    for permission in permissions:
        database_session.add(
            RolePermission(role_id=admin_role.id, permission_id=permission.id)
        )
        if permission.name == "door:read":
            database_session.add(
                RolePermission(role_id=user_role.id, permission_id=permission.id)
            )

    await database_session.commit()
    await database_session.refresh(admin_role)
    await database_session.refresh(user_role)
    return {"admin": admin_role, "user": user_role}


@pytest_asyncio.fixture
async def test_user(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> User:
    user = User(
        username="testuser",
        email="testuser@example.com",
        password_hash=hash_password("TestPassword123"),
        full_name="Test User",
        role_id=seeded_roles["user"].id,
        is_active=True,
    )
    database_session.add(user)
    await database_session.commit()
    await database_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_admin(
    database_session: AsyncSession,
    seeded_roles: dict[str, Role],
) -> User:
    admin = User(
        username="admin",
        email="admin@example.com",
        password_hash=hash_password("AdminPassword123"),
        full_name="Admin User",
        role_id=seeded_roles["admin"].id,
        is_active=True,
    )
    database_session.add(admin)
    await database_session.commit()
    await database_session.refresh(admin)
    return admin


@pytest.fixture(autouse=True)
def _patch_face_engine(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Prevent ONNX loading in tests. Engine returns no-face by default."""
    import src.faces.engine as engine_mod
    from src.faces.engine import get_engine

    mock = MagicMock()
    mock.detect_and_embed.return_value = None

    monkeypatch.setattr(engine_mod, "_engine", mock)
    monkeypatch.setattr(engine_mod, "load_engine", AsyncMock())
    monkeypatch.setattr(engine_mod, "unload_engine", AsyncMock())

    app.dependency_overrides[get_engine] = lambda: mock
    yield
    app.dependency_overrides.pop(get_engine, None)
