"""
HTTP client for the MCP Client Manager.

Wraps /tools (discovery) and /tools/invoke (execution).
All failures are non-fatal — the workflow proceeds without tool results
rather than crashing the task.
"""
from __future__ import annotations

import logging

import httpx

from .config import Settings

logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, settings: Settings) -> None:
        self._base = settings.mcp_client_manager_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=60.0)  # tools may be slow

    async def list_tools(self) -> list[dict]:
        """Return all available tools. Returns [] on error."""
        try:
            resp = await self._client.get(f"{self._base}/tools")
            resp.raise_for_status()
            return resp.json().get("tools", [])
        except Exception as exc:
            logger.warning("MCP list_tools failed (non-fatal): %s", exc)
            return []

    async def invoke(
        self,
        tenant_id: str,
        user_role: str,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """
        Invoke a tool. Returns the raw ToolCallResponse dict.
        Returns {"is_error": True, "error": "..."} on any failure.
        """
        try:
            resp = await self._client.post(
                f"{self._base}/tools/invoke",
                json={
                    "tenant_id": tenant_id,
                    "user_role": user_role,
                    "server_name": server_name,
                    "tool_name": tool_name,
                    "arguments": arguments,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("MCP invoke failed (non-fatal): %s", exc)
            return {"server_name": server_name, "tool_name": tool_name,
                    "result": None, "error": str(exc), "is_error": True}

    async def close(self) -> None:
        await self._client.aclose()
