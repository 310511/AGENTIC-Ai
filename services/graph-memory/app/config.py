from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    graph_memory_host: str = Field("0.0.0.0")
    graph_memory_port: int = Field(8003)
    graph_memory_debug: bool = Field(False)

    # Neo4j connection
    neo4j_uri: str = Field("bolt://localhost:7687")
    neo4j_user: str = Field("neo4j")
    neo4j_password: str = Field(...)

    # Retrieval
    default_graph_limit: int = Field(20)
    default_graph_depth: int = Field(1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
