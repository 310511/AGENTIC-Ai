"""
Task runner — delegates to the orchestrator /run endpoint.

Each worker message carries a task payload. The runner:
  1. Marks the task in_progress.
  2. POSTs to the orchestrator /run (which drives the LangGraph workflow).
  3. Polls /status until the task reaches a terminal state.
  4. Handles retries with linear backoff up to max_retries.

The orchestrator already writes final status to Postgres, so the worker
only needs to trigger it and wait — no duplicated logic.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import async_sessionmaker

from .config import Settings
from .db import set_task_status

logger = logging.getLogger(__name__)

_TERMINAL = {"completed", "failed", "cancelled"}
_POLL_INTERVAL = 3    # seconds between status polls
_POLL_TIMEOUT  = 600  # seconds before giving up on a single attempt (local LLM can be slow)


async def run_task(
    payload: dict,
    settings: Settings,
    session_factory: async_sessionmaker,
    attempt: int = 1,
) -> bool:
    """
    Execute one task. Returns True on success, False on failure.

    `attempt` is 1-indexed. Backoff = attempt * retry_delay_seconds.
    """
    task_id   = payload["task_id"]
    tenant_id = payload["tenant_id"]
    title     = payload.get("title", "")
    description = payload.get("description", "")

    logger.info("Worker attempt=%d task_id=%s", attempt, task_id)

    try:
        await set_task_status(session_factory, task_id, "in_progress")
    except Exception as exc:
        logger.error("DB status update failed for %s: %s", task_id, exc)
        return False

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
    except Exception as exc:
        logger.error("Orchestrator /run failed for task %s: %s", task_id, exc)
        await set_task_status(session_factory, task_id, "failed",
                              error_message=f"Worker could not reach orchestrator: {exc}")
        return False

    # Poll orchestrator /status until terminal or timeout.
    deadline = asyncio.get_event_loop().time() + _POLL_TIMEOUT
    final_status = None
    async with httpx.AsyncClient(timeout=10.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                r = await client.get(f"{orchestrator}/status/{task_id}")
                if r.status_code == 200:
                    data = r.json()
                    final_status = data.get("status")
                    if final_status in _TERMINAL:
                        logger.info("Task %s reached status=%s", task_id, final_status)
                        return final_status == "completed"
            except Exception as exc:
                logger.warning("Status poll error for %s: %s", task_id, exc)

    # Timed out waiting
    logger.error("Task %s timed out after %ds (attempt %d)", task_id, _POLL_TIMEOUT, attempt)
    await set_task_status(session_factory, task_id, "failed",
                          error_message=f"Worker timed out after {_POLL_TIMEOUT}s")
    return False
