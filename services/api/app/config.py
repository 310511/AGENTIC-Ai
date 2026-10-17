"""
Application configuration loaded from environment variables.

All required settings raise a clear error at startup if missing.
Never import secrets directly — always go through this module.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Typed settings loaded from environment variables (or a .env file).

    Required variables have no default; the app will refuse to start if
    they are absent, preventing silent misconfiguration.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    api_host: str = Field("0.0.0.0", description="Bind address")
    api_port: int = Field(8000, ge=1, le=65535)
    api_debug: bool = Field(False)
    api_cors_origins: str = Field(
        "http://localhost:3000",
        description="Allowed CORS origins (comma-separated)",
    )

    # ── Supabase / Auth ───────────────────────────────────────────────
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anon/public key")
    supabase_service_role_key: str = Field(..., description="Supabase service-role key (server only)")
    supabase_jwt_secret: str = Field(..., description="JWT secret for verifying Supabase tokens")

    # ── Database ──────────────────────────────────────────────────────
    database_url: str = Field(..., description="PostgreSQL connection string")

    # ── Redis ─────────────────────────────────────────────────────────
    redis_url: str = Field("redis://redis:6379/0")

    # ── Neo4j ─────────────────────────────────────────────────────────
    neo4j_uri: str = Field("bolt://neo4j:7687")
    neo4j_user: str = Field("neo4j")
    neo4j_password: str = Field(..., description="Neo4j password")

    # ── RabbitMQ ──────────────────────────────────────────────────────
    rabbitmq_url: str = Field("amqp://guest:guest@rabbitmq:5672/")

    # ── Observability ─────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = Field("http://otel-collector:4317")
    otel_service_name: str = Field("ai-agent-api")

    # ── Internal services ─────────────────────────────────────────────
    orchestrator_url: str = Field("http://orchestrator:8001")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]




@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    Using lru_cache means we parse env vars once at startup.
    In tests, call get_settings.cache_clear() before overriding settings.
    """
    return Settings()
