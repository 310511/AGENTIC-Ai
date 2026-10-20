from __future__ import annotations
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    orchestrator_host: str = Field("0.0.0.0")
    orchestrator_port: int = Field(8001)
    orchestrator_debug: bool = Field(False)

    # Ollama
    ollama_base_url: str = Field("http://ollama:11434")
    default_llm_model: str = Field("llama3.2")
    llm_timeout: int = Field(120, description="Per-request LLM timeout in seconds")
    llm_max_retries: int = Field(3)

    # Shared DB (same Postgres as API — orchestrator updates task status)
    database_url: str = Field(...)

    # Internal API base URL (orchestrator calls back to update task status)
    api_internal_url: str = Field("http://api:8000")

    # Knowledge service
    knowledge_url: str = Field("http://localhost:8002")
    knowledge_top_k: int = Field(5)

    # Graph memory service
    graph_memory_url: str = Field("http://localhost:8003")

    # MCP Client Manager
    mcp_client_manager_url: str = Field("http://localhost:8004")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
