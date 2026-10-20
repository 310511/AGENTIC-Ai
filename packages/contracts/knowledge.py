"""
Knowledge Service contracts — shared between the knowledge service
and any caller (orchestrator, api).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    """Ingest a document into the knowledge base."""

    tenant_id: UUID = Field(..., description="Tenant that owns this document")
    document_id: str = Field(
        ...,
        description="Stable caller-assigned ID (e.g. Supabase Storage path or UUID)",
    )
    title: str = Field(..., max_length=512)
    content: str = Field(..., description="Plain text content to embed and index")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller metadata stored alongside chunks",
    )


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int


# ── Retrieve ──────────────────────────────────────────────────────────────────

class RetrieveRequest(BaseModel):
    """Vector similarity search for relevant chunks."""

    tenant_id: UUID = Field(..., description="Scopes results to this tenant")
    query: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(5, ge=1, le=20)


class ChunkResult(BaseModel):
    document_id: str
    chunk_index: int
    text: str
    score: float = Field(..., description="Cosine similarity score (higher = more relevant)")
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[ChunkResult]


# ── NLP extraction ────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    """Run spaCy NER + entity extraction on text."""

    text: str = Field(..., max_length=50_000)


class EntityResult(BaseModel):
    text: str
    label: str   # e.g. PERSON, ORG, GPE
    start: int
    end: int


class ExtractResponse(BaseModel):
    entities: list[EntityResult]
    sentences: list[str]
