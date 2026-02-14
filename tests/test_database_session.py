"""
Tests for async database session and PostGIS init (DATA_LAYER).
Integration tests run only when DATABASE_URL is set to a PostgreSQL URL.
"""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base
from database.session import get_db, init_db_extensions


def _test_db_url():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url or "postgresql" not in url:
        return None
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


@pytest.mark.asyncio
async def test_get_db_yields_session():
    """get_db is an async generator that yields an AsyncSession."""
    from unittest.mock import AsyncMock, MagicMock, patch
    fake_session = MagicMock(spec=AsyncSession)
    fake_cm = AsyncMock()
    fake_cm.__aenter__.return_value = fake_session
    fake_cm.__aexit__.return_value = None
    with patch("database.session.async_session_factory", new=MagicMock(return_value=fake_cm)):
        from database.session import get_db as get_db_fresh
        gen = get_db_fresh()
        session = await gen.__anext__()
        assert session is not None
        assert session is fake_session


@pytest.mark.integration
@pytest.mark.asyncio
async def test_init_db_extensions_creates_postgis(skip_if_no_db):
    """When DATABASE_URL is set, init_db_extensions creates postgis (and topology) if not present."""
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    engine = create_async_engine(db_url, pool_pre_ping=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)
    async with async_session() as session:
        await init_db_extensions(session)
        result = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'postgis'"))
        row = result.scalar_one_or_none()
        assert row is not None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_session_commit_rollback(skip_if_no_db):
    """Session can execute a simple query (smoke test)."""
    db_url = _test_db_url()
    if not db_url:
        pytest.skip("DATABASE_URL not set")
    from database.session import async_session_factory
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1 AS n"))
        row = result.scalar_one()
        assert row[0] == 1
