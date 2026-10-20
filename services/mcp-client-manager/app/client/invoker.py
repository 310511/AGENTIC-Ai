"""
Tool invoker — calls a tool on a connected MCP server with timeout enforcement.

Security:
- Arguments are passed as-is to the MCP SDK; the SDK serialises them.
- Tool results are returned as untrusted data; callers must not use them
  for auth or policy decisions without independent validation.
- Policy and audit checks live in the caller (main.py), not here.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .manager import MCPServerManager

logger = logging.getLogger(__name__)


async def invoke_tool(
    manager: MCPServerManager,
    server_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    timeout: int,
) -> tuple[Any, str | None]:
    """
    Call *tool_name* on *server_name* and return (result, error).

    result is whatever the MCP server returns (list of content blocks).
    error is a human-readable string on failure, None on success.
    """
    try:
        session = manager.get_session(server_name)
    except KeyError as exc:
        return None, str(exc)

    try:
        raw = await asyncio.wait_for(
            session.call_tool(tool_name, arguments=arguments),
            timeout=timeout,
        )
        # raw.content is a list of content blocks (text, image, etc.)
        # Flatten to a list of dicts for easy serialisation.
        result = [
            {"type": block.type, "text": getattr(block, "text", None)}
            for block in (raw.content or [])
        ]
        is_error = getattr(raw, "isError", False)
        if is_error:
            return result, "Tool reported isError=True"
        return result, None
    except asyncio.TimeoutError:
        return None, f"Tool '{tool_name}' timed out after {timeout}s"
    except Exception as exc:
        logger.error("Tool invocation error server=%s tool=%s: %s", server_name, tool_name, exc)
        return None, str(exc)
