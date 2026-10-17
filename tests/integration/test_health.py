"""
Integration tests for /health and /ready endpoints.
"""
import pytest


@pytest.mark.integration
async def test_health_returns_200(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.integration
async def test_ready_returns_status(api_client):
    response = await api_client.get("/ready")
    data = response.json()
    # May be "ready" or "degraded" depending on infra availability.
    assert data["status"] in ("ready", "degraded")
    assert "checks" in data
    assert "database" in data["checks"]
    assert "redis" in data["checks"]
