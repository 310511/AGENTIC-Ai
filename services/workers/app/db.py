"""
Minimal async Postgres helpers for the workers service.

The workers only need to read/write task status — they don't use the
full ORM model to avoid duplicating SQLAlchemy models across services.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


def make_engine(database_url: str):
    url = (
        database_url
        .replace("postgresql://", "postgresql+asyncpg://", 1)
        .replace("postgres://",    "postgresql+asyncpg://", 1)
    )
    return create_async_engine(url, pool_pre_ping=True, pool_size=5)


async def set_task_status(
    session_factory: async_sessionmaker,
    task_id: str,
    new_status: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    values: dict = {
        "status":     new_status,
        "updated_at": datetime.now(tz=timezone.utc),
        "task_id":    task_id,
    }
    set_parts = ["status = :status", "updated_at = :updated_at"]

    if result is not None:
        import json
        values["result"] = json.dumps(result)
        set_parts.append("result = :result::jsonb")
    if error_message is not None:
        values["error_message"] = error_message
        set_parts.append("error_message = :error_message")
    if new_status == "completed":
        values["completed_at"] = datetime.now(tz=timezone.utc)
        set_parts.append("completed_at = :completed_at")

    async with session_factory() as session:
        await session.execute(
            text(f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = :task_id"),
            values,
        )
        await session.commit()
