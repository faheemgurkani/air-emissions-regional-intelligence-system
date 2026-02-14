"""
Async database engine and session factory.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings
from database.models import Base

# Convert postgresql+asyncpg URL; ensure no sync driver
_db_url = settings.database_url
if _db_url.startswith("postgresql://"):
    _db_url = _db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

async_engine = create_async_engine(
    _db_url,
    echo=False,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db_extensions(session: AsyncSession) -> None:
    """Create PostGIS extensions if not present. Run once after DB is up."""
    from sqlalchemy import text
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    await session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis_topology"))
    await session.commit()
