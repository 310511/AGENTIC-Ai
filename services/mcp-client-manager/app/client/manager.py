"""
MCP server registry and connection lifecycle.

Each configured server is launched as a subprocess (stdio transport) on
first use and kept alive for the process lifetime. list_tools() queries
every connected server and returns a merged catalogue.

The manager is a singleton created at startup and closed on shutdown.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from ..config import Settings

logger = logging.getLogger(__name__)


class ServerHandle:
    """Holds the live streams and session for one MCP server subprocess."""

    def __init__(self, name: str, session: ClientSession) -> None:
        self.name = name
        self.session = session


class MCPServerManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._handles: dict[str, ServerHandle] = {}
        # Keep the async context managers alive for the process lifetime.
        self._cms: list[Any] = []

    async def start(self) -> None:
        """Launch all configured servers and open ClientSessions."""
        for srv in self._settings.parsed_servers():
            name = srv["name"]
            try:
                await self._connect(name, srv)
                logger.info("MCP server connected: %s", name)
            except Exception as exc:
                # Non-fatal: log and skip unavailable servers.
                logger.warning("MCP server '%s' failed to start: %s", name, exc)

    async def _connect(self, name: str, srv: dict) -> None:
        params = StdioServerParameters(
            command=srv["command"],
            args=srv.get("args", []),
            env=srv.get("env"),
        )
        # Open the stdio streams and keep the context manager alive.
        cm = stdio_client(params)
        read, write = await cm.__aenter__()
        self._cms.append(cm)

        session_cm = ClientSession(read, write)
        session = await session_cm.__aenter__()
        self._cms.append(session_cm)

        await session.initialize()
        self._handles[name] = ServerHandle(name=name, session=session)

    async def close(self) -> None:
        for cm in reversed(self._cms):
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._handles.clear()
        self._cms.clear()

    # ── queries ───────────────────────────────────────────────────────────────

    async def list_tools(self) -> list[dict]:
        """Return tool descriptors from all connected servers."""
        tools: list[dict] = []
        for name, handle in self._handles.items():
            try:
                result = await handle.session.list_tools()
                for t in result.tools:
                    tools.append({
                        "server_name": name,
                        "tool_name": t.name,
                        "description": t.description or "",
                        "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
                    })
            except Exception as exc:
                logger.warning("list_tools failed for server '%s': %s", name, exc)
        return tools

    def get_session(self, server_name: str) -> ClientSession:
        """Return the live session for a server, or raise KeyError."""
        if server_name not in self._handles:
            raise KeyError(f"MCP server '{server_name}' not connected.")
        return self._handles[server_name].session

    @property
    def connected_servers(self) -> list[str]:
        return list(self._handles.keys())
