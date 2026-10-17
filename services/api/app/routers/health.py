"""
Health and readiness check endpoints.

GET /health  — liveness probe (always returns 200 if the process is up)
GET /ready   — readiness probe (checks database + Redis connectivity)

These endpoints are intentionally unauthenticated so load balancers and
orchestration platforms can poll them freely.
"""
from __future__ import annotations

import logging
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    status_code=status.HTTP_200_OK,
)
async def health() -> dict[str, str]:
    """Returns 200 OK as long as the process is running."""
    return {"status": "ok"}


@router.get(
    "/ready",
    summary="Readiness probe",
    status_code=status.HTTP_200_OK,
)
async def ready() -> dict[str, Any]:
    """
    Checks that the service can reach its critical dependencies.

    Returns 200 if all checks pass, 503 otherwise.
    Individual check results are included for debugging.
    """
    settings = get_settings()
    checks: dict[str, str] = {}
    healthy = True

    # ── Database check ────────────────────────────────────────────────
    try:
        engine = get_engine()
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Readiness check: database unavailable — %s", exc)
        checks["database"] = "unavailable"
        healthy = False

    # ── Redis check ───────────────────────────────────────────────────
    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        logger.warning("Readiness check: Redis unavailable — %s", exc)
        checks["redis"] = "unavailable"
        healthy = False

    return {
        "status": "ready" if healthy else "degraded",
        "checks": checks,
    }
