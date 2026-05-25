from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.core.config import get_settings
import src.core.database as db


@pytest_asyncio.fixture(autouse=True)
async def reset_db() -> AsyncGenerator[None, None]:
    await db.close_db()
    yield
    await db.close_db()


@pytest.mark.asyncio
async def test_database_engine_uses_configured_async_sqlite_url() -> None:
    assert db.engine is None
    assert db.async_session is None


@pytest.mark.asyncio
async def test_database_init_creates_engine_and_sessionmaker() -> None:
    await db.init_db()

    assert isinstance(db.engine, AsyncEngine)
    assert str(db.engine.url) == get_settings().DATABASE_URL
    assert "test_sealgate.db" in str(db.engine.url)
    assert db.async_session is not None
    assert db.async_session.kw["expire_on_commit"] is False


@pytest.mark.asyncio
async def test_get_session_yields_async_session() -> None:
    await db.init_db()
    session_generator = db.get_session()

    assert isinstance(session_generator, AsyncGenerator)

    session = await anext(session_generator)
    try:
        assert isinstance(session, AsyncSession)
    finally:
        await session_generator.aclose()


@pytest.mark.asyncio
async def test_get_session_requires_initialized_database() -> None:
    await db.close_db()

    session_generator = db.get_session()

    with pytest.raises(RuntimeError, match="Database is not initialized"):
        await anext(session_generator)


@pytest.mark.asyncio
async def test_create_db_and_tables_requires_initialized_database() -> None:
    with pytest.raises(RuntimeError, match="Database is not initialized"):
        await db.create_db_and_tables()


@pytest.mark.asyncio
async def test_init_and_close_db_are_awaitable() -> None:
    assert await db.init_db() is None
    assert await db.close_db() is None
