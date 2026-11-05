"""
Document ingest and management endpoints.

Routes:
  POST   /documents/ingest         — chunk, embed, and index a document (text)
  POST   /documents/upload         — upload PDF/image, extract text, chunk, embed, index
  POST   /documents/search         — semantic search across tenant's documents
  DELETE /documents/{document_id}  — remove a document from the knowledge index

All routes are JWT-protected and tenant-scoped.
"""
from __future__ import annotations

import logging
import uuid as _uuid
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..config import get_settings
from ..dependencies import CurrentUser, get_http_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


# ── local schemas (mirror contracts/knowledge.py) ─────────────────────────────

class IngestRequest(BaseModel):
    document_id: str = Field(..., description="Stable ID for this document; re-ingest replaces it")
    title: str = Field(..., max_length=512)
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestResponse(BaseModel):
    document_id: str
    chunks_indexed: int


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2048)
    top_k: int = Field(5, ge=1, le=20)


class ChunkResult(BaseModel):
    document_id: str
    chunk_index: int
    text: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    chunks: list[ChunkResult]


# ── helpers ───────────────────────────────────────────────────────────────────

async def _knowledge_post(
    client: httpx.AsyncClient,
    path: str,
    body: dict,
) -> dict:
    knowledge_url = get_settings().knowledge_url.rstrip("/")
    try:
        resp = await client.post(f"{knowledge_url}{path}", json=body, timeout=60.0)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text,
        ) from exc
    except Exception as exc:
        logger.error("Knowledge service error on %s: %s", path, exc)
        raise HTTPException(status_code=503, detail="Knowledge service unavailable") from exc


# ── routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Index a document into the knowledge base",
)
async def ingest_document(
    payload: IngestRequest,
    user: CurrentUser,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> IngestResponse:
    """
    Chunk, embed, and index a document scoped to the authenticated user's tenant.

    Re-ingesting an existing document_id replaces it atomically.
    """
    data = await _knowledge_post(http, "/ingest", {
        "tenant_id":   str(user.tenant_id),
        "document_id": payload.document_id,
        "title":       payload.title,
        "content":     payload.content,
        "metadata":    payload.metadata,
    })
    logger.info(
        "Document ingested: id=%s tenant=%s chunks=%s",
        payload.document_id, user.tenant_id, data.get("chunks_indexed"),
    )
    return IngestResponse(**data)


@router.post(
    "/upload",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a PDF or image and index it into the knowledge base",
)
async def upload_document(
    user: CurrentUser,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    file: UploadFile = File(...),
    title: str = Form(...),
    document_id: str = Form(default=""),
) -> IngestResponse:
    """
    Upload a PDF or image file. The knowledge service extracts text
    (pdfplumber for PDFs, pytesseract OCR for images), chunks it,
    embeds it, and stores it in FAISS — all scoped to the user's tenant.

    Supported: PDF, PNG, JPG, TIFF, BMP, WEBP (max 50 MB).
    """
    doc_id = document_id.strip() or str(_uuid.uuid4())
    knowledge_url = get_settings().knowledge_url.rstrip("/")

    file_bytes = await file.read()
    try:
        resp = await http.post(
            f"{knowledge_url}/ingest-file",
            data={
                "tenant_id":   str(user.tenant_id),
                "document_id": doc_id,
                "title":       title,
            },
            files={"file": (file.filename, file_bytes, file.content_type)},
            timeout=120.0,  # OCR on large PDFs can be slow
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        logger.error("File upload to knowledge service failed: %s", exc)
        raise HTTPException(status_code=503, detail="Knowledge service unavailable") from exc

    logger.info(
        "File uploaded: id=%s tenant=%s filename=%s chunks=%s",
        doc_id, user.tenant_id, file.filename, data.get("chunks_indexed"),
    )
    return IngestResponse(**data)


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search across tenant's documents",
)
async def search_documents(
    payload: SearchRequest,
    user: CurrentUser,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> SearchResponse:
    """Return the most semantically relevant chunks for a query, tenant-scoped."""
    data = await _knowledge_post(http, "/retrieve", {
        "tenant_id": str(user.tenant_id),
        "query":     payload.query,
        "top_k":     payload.top_k,
    })
    return SearchResponse(
        query=data["query"],
        chunks=[ChunkResult(**c) for c in data["chunks"]],
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Remove a document from the knowledge index",
)
async def delete_document(
    document_id: str,
    user: CurrentUser,
    http: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> dict:
    """Remove all indexed chunks for a document. Tenant-scoped."""
    knowledge_url = get_settings().knowledge_url.rstrip("/")
    try:
        resp = await http.delete(
            f"{knowledge_url}/documents/{document_id}",
            params={"tenant_id": str(user.tenant_id)},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except Exception as exc:
        logger.error("Knowledge delete error: %s", exc)
        raise HTTPException(status_code=503, detail="Knowledge service unavailable") from exc
