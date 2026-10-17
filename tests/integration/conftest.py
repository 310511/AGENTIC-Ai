"""
Integration test fixtures.

These tests require real infrastructure (PostgreSQL, Redis).
Run them with:
    docker compose -f infra/docker-compose.yml up -d postgres redis
    pytest -m integration

They are excluded from fast/unit test runs with:
    pytest -m "not integration"
"""
from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import the app factory and settings.
# Adjust sys.path as needed depending on your runner setup.
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

from app.main import create_app
from app.database import Base, get_db
from app.config import get_settings, Settings


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres_dev_password@localhost:5432/agent_platform",
)


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine (session-scoped)."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a test database session, rolled back after each test."""
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture()
async def api_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client for the FastAPI app.

    Overrides get_db to use the test session and overrides get_settings
    to inject test-safe configuration.
    """
    test_settings = Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwt_secret="test-jwt-secret-that-is-long-enough-for-hs256",
        database_url=TEST_DB_URL.replace("postgresql+asyncpg://", "postgresql://"),
        neo4j_password="test-neo4j-password",
    )

    async def override_get_db():
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    get_settings.cache_clear()

    with patch("app.config.get_settings", return_value=test_settings):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client

    app.dependency_overrides.clear()
