"""
Tool invocation audit log.

Writes structured log entries for every tool call attempt, whether it
succeeded, failed, or was denied. Sensitive argument values are not
logged — only argument keys are recorded.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("mcp.audit")


def log_invocation(
    tenant_id: str,
    user_role: str,
    server_name: str,
    tool_name: str,
    argument_keys: list[str],
    success: bool,
    error: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Emit one structured audit record."""
    logger.info(
        "tool_invocation tenant=%s role=%s server=%s tool=%s args=%s "
        "success=%s error=%s duration_ms=%s ts=%s",
        tenant_id,
        user_role,
        server_name,
        tool_name,
        argument_keys,          # keys only — no values
        success,
        error or "",
        f"{duration_ms:.1f}" if duration_ms is not None else "",
        datetime.now(tz=timezone.utc).isoformat(),
    )
