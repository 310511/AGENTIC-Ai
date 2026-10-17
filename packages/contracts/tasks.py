"""
Task schemas shared across services.

A "task" is the top-level unit of work submitted by a user and
orchestrated by the agent platform.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Lifecycle states of a task."""

    PENDING = "pending"         # Accepted, not yet picked up
    QUEUED = "queued"           # In the job queue
    IN_PROGRESS = "in_progress" # Actively being processed
    AWAITING_APPROVAL = "awaiting_approval"  # Paused for human approval
    COMPLETED = "completed"     # Finished successfully
    FAILED = "failed"           # Terminated with an error
    CANCELLED = "cancelled"     # Explicitly cancelled by the user


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class TaskCreate(BaseModel):
    """Payload accepted when a user submits a new task."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Short human-readable title for the task",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=4096,
        description="Full description of what the agent should accomplish",
    )
    priority: TaskPriority = Field(
        TaskPriority.NORMAL,
        description="Execution priority hint",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller-supplied metadata (treated as untrusted)",
    )

    model_config = {"populate_by_name": True}


class TaskUpdate(BaseModel):
    """Partial update payload for an existing task."""

    title: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = Field(None, min_length=1, max_length=4096)
    priority: TaskPriority | None = None
    metadata: dict[str, Any] | None = None


class TaskRead(BaseModel):
    """
    Full task representation returned to the caller.

    All IDs are server-assigned; never trust client-supplied IDs as
    proof of ownership.
    """

    id: UUID = Field(..., description="Server-assigned task UUID")
    tenant_id: UUID = Field(..., description="Tenant that owns this task")
    created_by: UUID = Field(..., description="User UUID who created the task")

    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus

    result: dict[str, Any] | None = Field(
        None, description="Final result payload, populated on completion"
    )
    error_message: str | None = Field(
        None, description="Human-readable error, populated on failure"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"populate_by_name": True, "from_attributes": True}


class TaskListResponse(BaseModel):
    """Paginated list of tasks."""

    items: list[TaskRead]
    total: int = Field(..., description="Total matching tasks across all pages")
    page: int
    page_size: int
