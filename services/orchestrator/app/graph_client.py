"""
HTTP client for the Graph Memory Service.

Wraps /retrieve (pre-planning context) and /store (post-execution persistence).
All failures are non-fatal — the workflow continues without graph context rather
than crashing the task.
"""
from __future__ import annotations

import logging

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class GraphClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.graph_memory_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=30.0)

    async def retrieve(self, tenant_id: str, query: str) -> str:
        """
        Return a summary string of relevant graph context for *query*.

        Returns "" on any error.
        """
        try:
            resp = await self._client.post(
                f"{self._base}/retrieve",
                json={"tenant_id": tenant_id, "query": query},
            )
            resp.raise_for_status()
            return resp.json().get("summary", "")
        except Exception as exc:
            logger.warning("Graph retrieval failed (non-fatal): %s", exc)
            return ""

    async def store(
        self,
        tenant_id: str,
        entities: list[dict],
        relationships: list[dict] | None = None,
    ) -> None:
        """
        Persist extracted entities/relationships. Fire-and-forget — failures logged only.
        """
        try:
            await self._client.post(
                f"{self._base}/store",
                json={
                    "tenant_id": tenant_id,
                    "entities": entities,
                    "relationships": relationships or [],
                },
            )
        except Exception as exc:
            logger.warning("Graph store failed (non-fatal): %s", exc)

    async def close(self) -> None:
        await self._client.aclose()
