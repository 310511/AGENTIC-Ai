"""
Graph Memory Service — FastAPI entry point (Phase 4).

Internal endpoints (not exposed to the public internet):
  POST   /store              — persist entities + relationships from a document
  POST   /retrieve           — fetch relevant entities/relationships for a query
  DELETE /documents/{id}     — remove a document's graph data
  GET    /health             — liveness + Neo4j connectivity check
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .config import get_settings
from .graph_store import GraphStore

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()
_store: GraphStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _store
    _store = GraphStore(settings)
    try:
        await _store.verify_connectivity()
        logger.info(
            "Graph memory service ready — neo4j=%s", settings.neo4j_uri
        )
    except Exception as exc:
        # Non-fatal at startup: service starts but /health will report degraded.
        logger.warning("Neo4j connectivity check failed: %s", exc)
    yield
    if _store:
        await _store.close()


app = FastAPI(
    title="Graph Memory Service",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


# ── local schemas (mirror contracts/graph.py — kept local so this service
#    has no import dependency on packages/contracts) ──────────────────────────

class GraphEntity(BaseModel):
    text: str
    label: str
    source_document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphRelationship(BaseModel):
    source_text: str
    source_label: str
    target_text: str
    target_label: str
    relation_type: str
    source_document_id: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphStoreRequest(BaseModel):
    tenant_id: UUID
    entities: list[GraphEntity]
    relationships: list[GraphRelationship] = Field(default_factory=list)


class GraphStoreResponse(BaseModel):
    entities_merged: int
    relationships_merged: int


class GraphRetrieveRequest(BaseModel):
    tenant_id: UUID
    query: str = Field(..., min_length=1, max_length=512)
    depth: int = Field(1, ge=1, le=3)
    limit: int = Field(20, ge=1, le=100)


class GraphRetrieveResponse(BaseModel):
    entities: list[GraphEntity]
    relationships: list[GraphRelationship]
    summary: str = ""


class GraphDeleteResponse(BaseModel):
    source_document_id: str
    nodes_deleted: int


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_ready():
    if _store is None:
        raise HTTPException(status_code=503, detail="Graph memory service not ready")


def _build_summary(
    entities: list[dict], relationships: list[dict]
) -> str:
    """Compact human-readable string for LLM context injection."""
    if not entities:
        return ""
    ent_str = ", ".join(f"{e['text']} ({e['label']})" for e in entities[:10])
    rel_str = ""
    if relationships:
        rel_str = "; ".join(
            f"{r['source_text']} {r['relation_type']} {r['target_text']}"
            for r in relationships[:10]
        )
        rel_str = f" Relationships: {rel_str}."
    return f"Known entities: {ent_str}.{rel_str}"


# ── routes ────────────────────────────────────────────────────────────────────

@app.post("/store", response_model=GraphStoreResponse, status_code=status.HTTP_201_CREATED)
async def store(req: GraphStoreRequest):
    """Merge entities and relationships extracted from a document into the graph."""
    _require_ready()

    entities_data = [e.model_dump() for e in req.entities]
    rels_data = [r.model_dump() for r in req.relationships]

    merged_e = await _store.merge_entities(str(req.tenant_id), entities_data)
    merged_r = await _store.merge_relationships(str(req.tenant_id), rels_data)

    logger.info(
        "Stored tenant=%s entities=%d relationships=%d",
        req.tenant_id, merged_e, merged_r,
    )
    return GraphStoreResponse(entities_merged=merged_e, relationships_merged=merged_r)


@app.post("/retrieve", response_model=GraphRetrieveResponse)
async def retrieve(req: GraphRetrieveRequest):
    """Return entities and relationships relevant to the query, scoped to tenant."""
    _require_ready()

    # Split query into terms for multi-word matching.
    terms = [t for t in req.query.split() if len(t) > 2]
    if not terms:
        terms = [req.query]

    raw = await _store.retrieve(
        str(req.tenant_id), terms, req.depth, req.limit
    )

    entities = [GraphEntity(**e) for e in raw["entities"]]
    relationships = [GraphRelationship(**r) for r in raw["relationships"]]
    summary = _build_summary(raw["entities"], raw["relationships"])

    return GraphRetrieveResponse(
        entities=entities,
        relationships=relationships,
        summary=summary,
    )


@app.delete("/documents/{document_id}", response_model=GraphDeleteResponse)
async def delete_document(document_id: str, tenant_id: UUID):
    """Remove graph data originating from a document."""
    _require_ready()
    deleted = await _store.delete_by_document(str(tenant_id), document_id)
    return GraphDeleteResponse(source_document_id=document_id, nodes_deleted=deleted)


@app.get("/health")
async def health():
    if _store is None:
        return {"status": "starting"}
    try:
        await _store.verify_connectivity()
        return {"status": "ok"}
    except Exception as exc:
        # Return 200 with degraded status — let orchestrator decide how to handle.
        return {"status": "degraded", "detail": str(exc)}
