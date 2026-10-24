"""
Task CRUD endpoints.

All routes are protected by JWT authentication.
Tenant isolation is enforced at the service layer (defence in depth on
top of PostgreSQL RLS).

Routes:
  POST   /tasks          — submit a new task
  GET    /tasks          — list tasks for the current user's tenant
  GET    /tasks/{id}     — get a single task
  PATCH  /tasks/{id}     — update task metadata (owner or operator)
  DELETE /tasks/{id}     — cancel a task (owner or admin)
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.rbac import require_same_tenant
from auth.exceptions import InsufficientPermissionsError
from contracts.common import APIResponse, PaginationParams
from contracts.tasks import (
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskStatus,
    TaskUpdate,
)
from contracts.users import UserContext, UserRole

from ..database import get_db
from ..dependencies import CurrentUser, OperatorUser, get_http_client
from ..models.task import Task
from ..config import get_settings


async def _trigger_orchestrator(
    client: httpx.AsyncClient,
    task_id: str,
    tenant_id: str,
    title: str,
    description: str,
) -> None:
    """Fire-and-forget POST to the orchestrator /run endpoint."""
    orchestrator_url = get_settings().orchestrator_url
    try:
        await client.post(
            f"{orchestrator_url}/run",
            json={
                "task_id": task_id,
                "tenant_id": tenant_id,
                "title": title,
                "description": description,
            },
        )
    except Exception as exc:
        # Log but never fail the API response — the task is already saved.
        logger.warning("Could not reach orchestrator for task %s: %s", task_id, exc)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _task_to_read(task: Task) -> TaskRead:
    """Map the ORM model to the public read schema."""
    return TaskRead(
        id=task.id,
        tenant_id=task.tenant_id,
        created_by=task.created_by,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        result=task.result,
        error_message=task.error_message,
        metadata=task.metadata_,
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
    )


async def _get_task_or_404(
    task_id: uuid.UUID,
    db: AsyncSession,
    user: UserContext,
) -> Task:
    """
    Fetch a task by ID and assert tenant ownership.

    Raises 404 (not 403) on missing-or-wrong-tenant to avoid leaking
    the existence of resources owned by other tenants.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    try:
        require_same_tenant(user, task.tenant_id)
    except InsufficientPermissionsError:
        # Return 404 to avoid leaking cross-tenant resource existence.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return task


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[TaskRead],
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new task",
)
async def create_task(
    payload: TaskCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> APIResponse[TaskRead]:
    """
    Accept a task submission from an authenticated user.

    Saves the task as PENDING, then fires a background call to the
    orchestrator which processes it asynchronously.
    """
    task = Task(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        created_by=user.user_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        status=TaskStatus.PENDING,
        metadata_=payload.metadata,
    )
    db.add(task)
    await db.flush()  # Get the DB-assigned timestamps without committing yet.
    await db.refresh(task)

    logger.info(
        "Task created: id=%s tenant=%s user=%s",
        task.id, task.tenant_id, user.user_id,
    )
    background_tasks.add_task(
        _trigger_orchestrator, http,
        str(task.id), str(task.tenant_id), task.title, task.description,
    )
    return APIResponse(success=True, data=_task_to_read(task))


@router.get(
    "",
    response_model=APIResponse[TaskListResponse],
    summary="List tasks for current tenant",
)
async def list_tasks(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: TaskStatus | None = Query(None, alias="status"),
) -> APIResponse[TaskListResponse]:
    """Return a paginated list of tasks scoped to the current tenant."""
    pagination = PaginationParams(page=page, page_size=page_size)

    base_query = select(Task).where(Task.tenant_id == user.tenant_id)
    if status_filter is not None:
        base_query = base_query.where(Task.status == status_filter)

    # Count total matching rows.
    count_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = count_result.scalar_one()

    # Fetch paginated rows ordered by creation time (newest first).
    rows_result = await db.execute(
        base_query.order_by(Task.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    tasks = rows_result.scalars().all()

    return APIResponse(
        success=True,
        data=TaskListResponse(
            items=[_task_to_read(t) for t in tasks],
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@router.get(
    "/{task_id}",
    response_model=APIResponse[TaskRead],
    summary="Get a task by ID",
)
async def get_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[TaskRead]:
    task = await _get_task_or_404(task_id, db, user)
    return APIResponse(success=True, data=_task_to_read(task))


@router.patch(
    "/{task_id}",
    response_model=APIResponse[TaskRead],
    summary="Update task metadata",
)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[TaskRead]:
    """
    Update the mutable fields of a task.

    Only the task owner or an operator/admin may update a task.
    Completed, failed, and cancelled tasks cannot be updated.
    """
    task = await _get_task_or_404(task_id, db, user)

    # Restrict updates to owner or elevated roles.
    is_owner = task.created_by == user.user_id
    is_elevated = user.role in (UserRole.OPERATOR, UserRole.ADMIN)
    if not (is_owner or is_elevated):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the task owner or an operator may update this task",
        )

    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    if task.status in terminal_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot update a task in '{task.status}' status",
        )

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.metadata is not None:
        task.metadata_ = payload.metadata

    await db.flush()
    await db.refresh(task)

    logger.info("Task updated: id=%s by user=%s", task.id, user.user_id)
    return APIResponse(success=True, data=_task_to_read(task))


@router.delete(
    "/{task_id}",
    response_model=APIResponse[TaskRead],
    summary="Cancel a task",
)
async def cancel_task(
    task_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse[TaskRead]:
    """
    Mark a task as CANCELLED.

    Only the task owner or an admin may cancel a task.
    Already-terminal tasks cannot be cancelled.
    """
    task = await _get_task_or_404(task_id, db, user)

    is_owner = task.created_by == user.user_id
    is_admin = user.role == UserRole.ADMIN
    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the task owner or an admin may cancel this task",
        )

    terminal_statuses = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    if task.status in terminal_statuses:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already in terminal status '{task.status}'",
        )

    task.status = TaskStatus.CANCELLED

    await db.flush()
    await db.refresh(task)

    logger.info("Task cancelled: id=%s by user=%s", task.id, user.user_id)
    return APIResponse(success=True, data=_task_to_read(task))
