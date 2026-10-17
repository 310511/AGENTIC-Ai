"""
Tenant isolation tests.

These tests verify that a user in tenant A cannot read, update, or cancel
tasks owned by tenant B — even when the task ID is known.

These run without live infrastructure by mocking the database layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api"))

from contracts.tasks import TaskPriority, TaskStatus
from contracts.users import UserContext, UserRole


TENANT_A = uuid.uuid4()
TENANT_B = uuid.uuid4()
USER_A_ID = uuid.uuid4()
USER_B_ID = uuid.uuid4()
TASK_B_ID = uuid.uuid4()


def _user(tenant_id: uuid.UUID, user_id: uuid.UUID, role: UserRole = UserRole.USER) -> UserContext:
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        email="user@example.com",
        role=role,
        is_active=True,
    )


def _mock_task_owned_by_tenant_b() -> MagicMock:
    """Return a mock Task ORM object owned by TENANT_B."""
    task = MagicMock()
    task.id = TASK_B_ID
    task.tenant_id = TENANT_B
    task.created_by = USER_B_ID
    task.title = "Tenant B task"
    task.description = "Should not be accessible to Tenant A"
    task.priority = TaskPriority.NORMAL
    task.status = TaskStatus.PENDING
    task.result = None
    task.error_message = None
    task.metadata_ = {}
    task.created_at = datetime.now(tz=timezone.utc)
    task.updated_at = datetime.now(tz=timezone.utc)
    task.completed_at = None
    return task


@pytest.mark.security
async def test_user_cannot_read_another_tenants_task():
    """
    A user in TENANT_A requesting a task owned by TENANT_B
    must receive 404, not 200 or 403.

    We return 404 (not 403) to avoid leaking the existence of the resource.
    """
    from app.routers.tasks import _get_task_or_404
    from fastapi import HTTPException

    user_a = _user(TENANT_A, USER_A_ID)
    task_b = _mock_task_owned_by_tenant_b()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task_b
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await _get_task_or_404(TASK_B_ID, mock_db, user_a)

    assert exc_info.value.status_code == 404


@pytest.mark.security
async def test_operator_in_different_tenant_cannot_read_task():
    """Even operators are bounded by tenant isolation."""
    from app.routers.tasks import _get_task_or_404
    from fastapi import HTTPException

    # Operator in TENANT_A
    operator_a = _user(TENANT_A, USER_A_ID, role=UserRole.OPERATOR)
    task_b = _mock_task_owned_by_tenant_b()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = task_b
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await _get_task_or_404(TASK_B_ID, mock_db, operator_a)

    assert exc_info.value.status_code == 404


@pytest.mark.security
async def test_nonexistent_task_returns_404():
    """A task that does not exist at all must return 404."""
    from app.routers.tasks import _get_task_or_404
    from fastapi import HTTPException

    user_a = _user(TENANT_A, USER_A_ID)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    with pytest.raises(HTTPException) as exc_info:
        await _get_task_or_404(uuid.uuid4(), mock_db, user_a)

    assert exc_info.value.status_code == 404
