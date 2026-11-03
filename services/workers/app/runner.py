"""
Task runner — delegates to the orchestrator /run endpoint.

Design: fire-and-forget. The worker's job is to durably dequeue the
message and trigger the orchestrator. The orchestrator owns the full
workflow lifecycle and writes all status transitions to Postgres itself.

The worker does NOT poll for completion — that avoids the timeout race
where a slow LLM call causes the worker to mark a task failed while the
orchestrator is still happily running it.

Retry logic (in main.py) re-queues if the orchestrator /run POST itself
fails (network error, 503), not if the task eventually fails.
"""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from .config import Settings
from .db import set_task_status

logger = logging.getLogger(__name__)

_TERMINAL = {"completed", "failed", "cancelled"}


async def run_task(
    payload: dict,
    settings: Settings,
    session_factory: async_sessionmaker,
    attempt: int = 1,
) -> bool:
    """
    Trigger the orchestrator for one task. Returns True if the /run
    call was accepted (202), False if it failed (network error / 5xx).

    Status lifecycle is owned entirely by the orchestrator — the worker
    only marks in_progress before the trigger so the UI updates immediately.
    """
    task_id     = payload["task_id"]
    tenant_id   = payload["tenant_id"]
    title       = payload.get("title", "")
    description = payload.get("description", "")

    logger.info("Worker attempt=%d task_id=%s", attempt, task_id)

    # Mark in_progress immediately so the UI reflects activity.
    try:
        await set_task_status(session_factory, task_id, "in_progress")
    except Exception as exc:
        logger.error("DB status update failed for %s: %s", task_id, exc)
        # Non-fatal — orchestrator will set in_progress itself too.

    orchestrator = settings.orchestrator_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{orchestrator}/run",
                json={
                    "task_id":     task_id,
                    "tenant_id":   tenant_id,
                    "title":       title,
                    "description": description,
                },
            )
            resp.raise_for_status()
        logger.info("Task %s accepted by orchestrator (attempt %d)", task_id, attempt)
        return True
    except Exception as exc:
        logger.error("Orchestrator /run failed for task %s: %s", task_id, exc)
        # Only mark failed if the orchestrator couldn't even accept it.
        await set_task_status(
            session_factory, task_id, "failed",
            error_message=f"Could not reach orchestrator: {exc}",
        )
        return False
