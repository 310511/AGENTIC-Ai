"""
API-level authentication tests (unit, no infrastructure required).

Verifies that every protected endpoint enforces authentication and that
the correct HTTP status codes are returned for auth failures.
"""
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import create_app
from app.config import get_settings, Settings


@pytest.fixture()
def test_settings() -> Settings:
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_anon_key="test-anon-key",
        supabase_service_role_key="test-service-role-key",
        supabase_jwt_secret="test-jwt-secret-long-enough-for-hs256-here",
        database_url="postgresql://postgres:pass@localhost:5432/test",
        neo4j_password="test",
        api_debug=True,
    )


@pytest.fixture()
async def client(test_settings) -> AsyncClient:
    app = create_app()
    get_settings.cache_clear()
    with patch("app.config.get_settings", return_value=test_settings):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


PROTECTED_ENDPOINTS = [
    ("GET",    "/api/v1/tasks"),
    ("POST",   "/api/v1/tasks"),
    ("GET",    "/api/v1/tasks/00000000-0000-0000-0000-000000000001"),
    ("PATCH",  "/api/v1/tasks/00000000-0000-0000-0000-000000000001"),
    ("DELETE", "/api/v1/tasks/00000000-0000-0000-0000-000000000001"),
]


@pytest.mark.security
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_endpoint_requires_auth(client, method, path):
    """Every protected endpoint returns 401 when no token is supplied."""
    response = await client.request(method, path)
    assert response.status_code == 401, (
        f"{method} {path} returned {response.status_code}, expected 401"
    )


@pytest.mark.security
@pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
async def test_endpoint_rejects_garbage_token(client, method, path):
    """A garbage Bearer token must return 401."""
    response = await client.request(
        method, path, headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401


@pytest.mark.security
async def test_health_is_publicly_accessible(client):
    """Health endpoint must NOT require auth."""
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.security
async def test_ready_is_publicly_accessible(client):
    """Readiness endpoint must NOT require auth."""
    response = await client.get("/ready")
    # May be degraded if DB/Redis aren't running, but must not be 401.
    assert response.status_code != 401
