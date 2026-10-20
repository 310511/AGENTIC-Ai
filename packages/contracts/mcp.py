"""
MCP Client Manager contracts — shared between the mcp-client-manager service
and any caller (orchestrator).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """Describes one tool exposed by an MCP server."""
    server_name: str
    tool_name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ToolListResponse(BaseModel):
    tools: list[ToolInfo]


class ToolCallRequest(BaseModel):
    """Invoke a specific tool on a named MCP server."""
    tenant_id: UUID
    user_role: str = Field("user", description="Caller's role for policy check")
    server_name: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    server_name: str
    tool_name: str
    result: Any = None
    error: str | None = None
    is_error: bool = False
