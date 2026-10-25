from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ── Postgres ──────────────────────────────────────────────
    database_url: str = Field(..., description="PostgreSQL connection string")

    # ── RabbitMQ ──────────────────────────────────────────────
    rabbitmq_url: str = Field("amqp://guest:guest@localhost:5672/")

    # ── Queue names ───────────────────────────────────────────
    task_queue: str = Field("agent.tasks")
    dead_letter_queue: str = Field("agent.tasks.dlq")

    # ── Retry policy ──────────────────────────────────────────
    max_retries: int = Field(3, ge=1, le=10)
    retry_delay_seconds: int = Field(5, ge=1)  # multiplied by attempt number

    # ── Internal services ─────────────────────────────────────
    orchestrator_url: str = Field("http://localhost:8001")

    # ── Concurrency ───────────────────────────────────────────
    prefetch_count: int = Field(4, ge=1, le=32)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
