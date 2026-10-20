"""
HTTP client for the Knowledge Service.

Wraps /retrieve so the orchestrator can fetch relevant context chunks
before planning. Failures are non-fatal — the workflow continues with
an empty context rather than crashing the task.
"""
from __future__ import annotations

import logging

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class KnowledgeClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.knowledge_url.rstrip("/")
        self._top_k = settings.knowledge_top_k
        # Shared client — reused across requests, closed on shutdown.
        self._client = httpx.AsyncClient(timeout=30.0)

    async def retrieve(self, tenant_id: str, query: str) -> list[dict]:
        """
        Return top-k relevant chunks for *query* scoped to *tenant_id*.

        Returns [] on any error so callers never need to handle exceptions.
        """
        try:
            resp = await self._client.post(
                f"{self._base}/retrieve",
                json={"tenant_id": tenant_id, "query": query, "top_k": self._top_k},
            )
            resp.raise_for_status()
            return resp.json().get("chunks", [])
        except Exception as exc:
            # Non-fatal — orchestrator proceeds without retrieved context.
            logger.warning("Knowledge retrieval failed (non-fatal): %s", exc)
            return []

    async def close(self) -> None:
        await self._client.aclose()
