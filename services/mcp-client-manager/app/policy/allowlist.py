"""
Tool allowlist policy.

Checks happen before every tool invocation:
  1. Global allowlist (from config) — coarse filter, default * in dev.
  2. Role gate — operators and above may call any allowed tool;
     plain users are blocked from tools marked admin-only.

Never trust the LLM's claim that a tool call is permitted.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Tools that require at least operator role.
_OPERATOR_ONLY_TOOLS: frozenset[str] = frozenset()

# Tools that require admin role (irreversible / high-impact).
_ADMIN_ONLY_TOOLS: frozenset[str] = frozenset()


class PolicyError(Exception):
    """Raised when a tool call is denied by policy."""


def check_tool_allowed(
    tool_name: str,
    user_role: str,
    allowed_tools: set[str] | None,
) -> None:
    """
    Raise PolicyError if the call should be blocked.

    allowed_tools=None means the global allowlist is '*' (allow all).
    """
    # 1. Global allowlist check.
    if allowed_tools is not None and tool_name not in allowed_tools:
        raise PolicyError(
            f"Tool '{tool_name}' is not in the configured allowlist."
        )

    # 2. Role gate.
    role = user_role.lower()
    if tool_name in _ADMIN_ONLY_TOOLS and role != "admin":
        raise PolicyError(
            f"Tool '{tool_name}' requires admin role (caller has '{user_role}')."
        )
    if tool_name in _OPERATOR_ONLY_TOOLS and role not in ("admin", "operator"):
        raise PolicyError(
            f"Tool '{tool_name}' requires operator role (caller has '{user_role}')."
        )

    logger.debug("Policy OK: tool=%s role=%s", tool_name, user_role)
