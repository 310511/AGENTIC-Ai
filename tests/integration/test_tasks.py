"""
Integration tests for the /api/v1/tasks endpoints.

These tests exercise the full HTTP → FastAPI → SQLAlchemy → PostgreSQL
stack. They require a running database (see conftest.py).
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from auth.context import build_user_context
from auth.jwt import JWTClaims
from contracts.users import UserContext, UserRole


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user_context(role: UserRole = UserRole.USER) -> UserContext:
    return UserContext(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        email="integration@example.com",
        role=role,
        is_active=True,
    )


def _auth_headers(user_ctx: UserContext) -> dict:
    """
    Return headers that will pass the auth dependency.
    We patch get_current_user directly instead of minting real JWTs
    to keep integration tests independent of JWT secret config.
    """
    return {"Authorization": "Bearer test-token"}


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.integration
async def test_create_task_requires_auth(api_client):
    """Unauthenticated request must return 401."""
    response = await api_client.post(
        "/api/v1/tasks",
        json={"title": "Test", "description": "A test task"},
    )
    assert response.status_code == 401


@pytest.mark.integration
async def test_create_task_success(api_client):
    """Authenticated user can create a task."""
    user = _make_user_context()

    with patch("app.routers.tasks.CurrentUser", user), \
         patch("app.dependencies.get_current_user", return_value=user):

        response = await api_client.post(
            "/api/v1/tasks",
            json={
                "title": "Integration test task",
                "description": "Created by the integration test suite",
                "priority": "normal",
            },
            headers=_auth_headers(user),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    data = body["data"]
    assert data["title"] == "Integration test task"
    assert data["status"] == "pending"
    assert data["tenant_id"] == str(user.tenant_id)
    assert data["created_by"] == str(user.user_id)


@pytest.mark.integration
async def test_list_tasks_empty_for_new_tenant(api_client):
    """A new tenant sees an empty task list."""
    user = _make_user_context()

    with patch("app.dependencies.get_current_user", return_value=user):
        response = await api_client.get(
            "/api/v1/tasks",
            headers=_auth_headers(user),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 0
    assert body["data"]["items"] == []
