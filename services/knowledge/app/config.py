from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    knowledge_host: str = Field("0.0.0.0")
    knowledge_port: int = Field(8002)
    knowledge_debug: bool = Field(False)

    # Embedding model — locally cached, no download needed
    # BGE (768-dim) is the production target; MiniLM (384-dim) works offline.
    # shortcut: using all-MiniLM-L6-v2 (384-dim) instead of BAAI/bge-base-en-v1.5 (768-dim);
    #           swap back once BGE download completes, then delete data/faiss/ to rebuild index.
    embedding_model: str = Field("sentence-transformers/all-MiniLM-L6-v2")
    bge_query_prefix: str = Field("")  # MiniLM needs no prefix

    # Chunking
    chunk_size: int = Field(512, description="Max tokens per chunk")
    chunk_overlap: int = Field(64, description="Overlap between consecutive chunks")

    # FAISS index persistence — stored under this directory
    index_dir: Path = Field(Path("data/faiss"), description="Directory for FAISS index + ID map")

    # spaCy model
    spacy_model: str = Field("en_core_web_sm")

    # Retrieval
    default_top_k: int = Field(5)

    # Internal API URL (for orchestrator to call)
    knowledge_url: str = Field("http://localhost:8002")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
