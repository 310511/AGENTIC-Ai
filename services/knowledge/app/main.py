"""
Knowledge Service — FastAPI entry point (Phase 3).

Internal endpoints (not exposed to the public internet):
  POST /ingest          — chunk, embed, and index a document
  POST /retrieve        — vector similarity search (tenant-scoped)
  POST /extract         — spaCy NER + sentence splitting
  DELETE /documents/{id} — remove a document's vectors from the index
  GET  /health          — liveness check
"""
from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status

from .chunker import chunk_text
from .config import get_settings
from .embedder import Embedder
from .nlp import NLPProcessor
from .vector_store import VectorStore

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Module-level singletons — initialised in lifespan, never None after startup.
_embedder: Embedder | None = None
_store: VectorStore | None = None
_nlp: NLPProcessor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _embedder, _store, _nlp
    # Heavy model loads run in a thread so the event loop stays responsive.
    _embedder, _nlp = await asyncio.gather(
        asyncio.to_thread(Embedder, settings.embedding_model, settings.bge_query_prefix),
        asyncio.to_thread(NLPProcessor, settings.spacy_model),
    )
    _store = VectorStore(settings.index_dir)
    logger.info(
        "Knowledge service ready — model=%s spacy=%s index_dir=%s",
        settings.embedding_model,
        settings.spacy_model,
        settings.index_dir,
    )
    yield


app = FastAPI(
    title="Knowledge Service",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_ready():
    if _embedder is None or _store is None or _nlp is None:
        raise HTTPException(status_code=503, detail="Knowledge service not ready")


# ── schemas (local, to avoid importing the contracts package from inside the
#    service — contracts are used by callers, not internally) ─────────────────

from pydantic import BaseModel, Field
from typing import Any
from uuid import UUID


class IngestRequest(BaseModel):
    tenant_id: UUID
    document_id: str
    title: str = Field(..., max_length=512)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int


class RetrieveRequest(BaseModel):
    tenant_id: UUID
    query: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(5, ge=1, le=20)


class ChunkResult(BaseModel):
    document_id: str
    chunk_index: int
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    query: str
    chunks: list[ChunkResult]


class ExtractRequest(BaseModel):
    text: str = Field(..., max_length=50_000)


class EntityResult(BaseModel):
    text: str
    label: str
    start: int
    end: int


class ExtractResponse(BaseModel):
    entities: list[EntityResult]
    sentences: list[str]


# ── routes ────────────────────────────────────────────────────────────────────

@app.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest(req: IngestRequest):
    """
    Chunk, embed, and index a document.

    Re-ingesting the same document_id+tenant_id first removes the old
    vectors so the index stays consistent.
    """
    _require_ready()

    # Remove stale vectors for this document before re-indexing.
    _store.delete_document(req.document_id, str(req.tenant_id))

    chunks = chunk_text(req.content, settings.chunk_size, settings.chunk_overlap)
    texts = [c.text for c in chunks]

    vectors = await asyncio.to_thread(_embedder.embed_documents, texts)

    chunk_dicts = [
        {"index": c.index, "text": c.text, "metadata": {**req.metadata, "title": req.title}}
        for c in chunks
    ]
    added = _store.add(vectors, req.document_id, str(req.tenant_id), chunk_dicts)

    logger.info(
        "Ingested document_id=%s tenant=%s chunks=%d",
        req.document_id, req.tenant_id, added,
    )
    return IngestResponse(document_id=req.document_id, chunks_indexed=added)


@app.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(req: RetrieveRequest):
    """Embed the query with the BGE prefix, then return the top-k tenant-scoped chunks."""
    _require_ready()

    query_vec = await asyncio.to_thread(_embedder.embed_query, req.query)
    raw = _store.search(query_vec, str(req.tenant_id), req.top_k)

    chunks = [
        ChunkResult(
            document_id=r["document_id"],
            chunk_index=r["chunk_index"],
            text=r["text"],
            score=r["score"],
            metadata=r["metadata"],
        )
        for r in raw
    ]
    return RetrieveResponse(query=req.query, chunks=chunks)


@app.post("/extract", response_model=ExtractResponse)
async def extract(req: ExtractRequest):
    """Run spaCy NER and sentence splitting on arbitrary text."""
    _require_ready()
    result = await asyncio.to_thread(_nlp.extract, req.text)
    return ExtractResponse(
        entities=[EntityResult(**e) for e in result["entities"]],
        sentences=result["sentences"],
    )


@app.delete("/documents/{document_id}", status_code=status.HTTP_200_OK)
async def delete_document(document_id: str, tenant_id: UUID):
    """Remove all vectors for a document from the FAISS index."""
    _require_ready()
    removed = _store.delete_document(document_id, str(tenant_id))
    return {"document_id": document_id, "vectors_removed": removed}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "index_vectors": _store._index.ntotal if _store else 0,
    }
