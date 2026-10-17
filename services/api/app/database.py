"""
Async PostgreSQL database session management via SQLAlchemy.

We use SQLAlchemy's async engine backed by asyncpg.
Each request gets its own session, acquired through the FastAPI
dependency `get_db`. Sessions are committed or rolled back and closed
automatically at the end of the request.

Row-Level Security (RLS) notes:
- PostgreSQL RLS is defined in the Supabase schema and enforced at the
  database level for multi-tenant isolation.
- Always pass the authenticated user's JWT or a trusted service context
  when opening a session that should respect RLS.
- Do NOT bypass RLS by using the service-role key for user-facing
  operations; reserve that key for admin/migration tasks only.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

logger = logging.getLogger(__name__)

# Module-level engine and session factory; initialised once on startup.
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """
    Declarative base for all SQLAlchemy ORM models.

    Importing this in model modules registers them with the metadata.
    """
    pass


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call."""
    global _engine
    if _engine is None:
        settings = get_settings()
        # Convert a standard postgres:// URL to the asyncpg driver URL.
        url = settings.database_url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        ).replace(
            "postgres://", "postgresql+asyncpg://", 1
        )
        _engine = create_async_engine(
            url,
            echo=settings.api_debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        logger.info("Database engine created")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the shared session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an async database session per request.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """Dispose the engine pool. Called on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("Database engine disposed")
