"""
MCP Client Manager — FastAPI entry point (Phase 5).

Internal endpoints (not exposed to the public internet):
  GET  /tools              — list all tools from all connected MCP servers
  POST /tools/invoke       — invoke a tool (policy checked + audited)
  GET  /health             — liveness + connected server count
"""
from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .audit import log_invocation
from .client.invoker import invoke_tool
from .client.manager import MCPServerManager
from .config import get_settings
from .policy.allowlist import PolicyError, check_tool_allowed

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()
_manager: MCPServerManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _manager
    _manager = MCPServerManager(settings)
    await _manager.start()
    logger.info(
        "MCP Client Manager ready — servers=%s",
        _manager.connected_servers,
    )
    yield
    await _manager.close()


app = FastAPI(
    title="MCP Client Manager",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


# ── local schemas (mirror contracts/mcp.py) ───────────────────────────────────

class ToolInfo(BaseModel):
    server_name: str
    tool_name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]


class ToolCallRequest(BaseModel):
    tenant_id: UUID
    user_role: str = "user"
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    server_name: str
    tool_name: str
    result: Any = None
    error: str | None = None
    is_error: bool = False


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_ready():
    if _manager is None:
        raise HTTPException(status_code=503, detail="MCP Client Manager not ready")


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/tools", response_model=ToolListResponse)
async def list_tools():
    """Return all tools available across connected MCP servers."""
    _require_ready()
    raw = await _manager.list_tools()
    return ToolListResponse(tools=[ToolInfo(**t) for t in raw])


@app.post("/tools/invoke", response_model=ToolCallResponse)
async def invoke(req: ToolCallRequest):
    """
    Invoke a tool after policy check and emit an audit record.

    Returns 403 if the call is denied by policy.
    Returns 200 with is_error=True if the tool itself reports an error.
    """
    _require_ready()

    # ── policy check ──────────────────────────────────────────────────────────
    allowed = settings.allowed_tools()
    try:
        check_tool_allowed(req.tool_name, req.user_role, allowed)
    except PolicyError as exc:
        log_invocation(
            tenant_id=str(req.tenant_id),
            user_role=req.user_role,
            server_name=req.server_name,
            tool_name=req.tool_name,
            argument_keys=list(req.arguments.keys()),
            success=False,
            error=str(exc),
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    # ── invocation ────────────────────────────────────────────────────────────
    t0 = time.monotonic()
    result, error = await invoke_tool(
        _manager,
        req.server_name,
        req.tool_name,
        req.arguments,
        settings.tool_timeout,
    )
    duration_ms = (time.monotonic() - t0) * 1000

    # ── audit ─────────────────────────────────────────────────────────────────
    log_invocation(
        tenant_id=str(req.tenant_id),
        user_role=req.user_role,
        server_name=req.server_name,
        tool_name=req.tool_name,
        argument_keys=list(req.arguments.keys()),
        success=error is None,
        error=error,
        duration_ms=duration_ms,
    )

    return ToolCallResponse(
        server_name=req.server_name,
        tool_name=req.tool_name,
        result=result,
        error=error,
        is_error=error is not None,
    )


@app.get("/health")
async def health():
    servers = _manager.connected_servers if _manager else []
    return {"status": "ok", "connected_servers": servers}
