"""
Graph Memory Service contracts — shared between the graph-memory service
and any caller (orchestrator).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


# ── Entity / Relationship primitives ─────────────────────────────────────────

class GraphEntity(BaseModel):
    """A named entity extracted from text."""
    text: str = Field(..., description="Surface form, e.g. 'OpenAI'")
    label: str = Field(..., description="spaCy OntoNotes label, e.g. ORG, PERSON, GPE")
    source_document_id: str = Field(..., description="Document the entity came from")
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    """A directed relationship between two entities."""
    source_text: str
    source_label: str
    target_text: str
    target_label: str
    relation_type: str = Field(..., description="e.g. WORKS_FOR, LOCATED_IN, MENTIONED_WITH")
    source_document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Store (write) ─────────────────────────────────────────────────────────────

class GraphStoreRequest(BaseModel):
    """Persist entities (and optionally relationships) extracted from a document."""
    tenant_id: UUID
    entities: list[GraphEntity]
    relationships: list[GraphRelationship] = Field(default_factory=list)


class GraphStoreResponse(BaseModel):
    entities_merged: int
    relationships_merged: int


# ── Retrieve (read) ───────────────────────────────────────────────────────────

class GraphRetrieveRequest(BaseModel):
    """
    Return entities and their neighbours relevant to a query.

    Matches entities whose text contains any term in *query* (case-insensitive),
    then returns their direct neighbours up to *depth* hops.
    """
    tenant_id: UUID
    query: str = Field(..., min_length=1, max_length=512)
    depth: int = Field(1, ge=1, le=3, description="Relationship hops to traverse")
    limit: int = Field(20, ge=1, le=100)


class GraphRetrieveResponse(BaseModel):
    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    summary: str = Field("", description="Human-readable summary for LLM context injection")


# ── Delete ────────────────────────────────────────────────────────────────────

class GraphDeleteRequest(BaseModel):
    tenant_id: UUID
    source_document_id: str
