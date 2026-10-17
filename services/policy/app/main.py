"""
Policy Service — entry point (Phase 5+ placeholder).

Basic RBAC is already implemented in packages/auth/rbac.py and used
inline by the API service. This standalone service will be introduced
when the Orchestrator and MCP Client Manager require runtime policy checks.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Policy service is a Phase 5+ placeholder — "
        "RBAC helpers are currently in packages/auth/rbac.py."
    )


if __name__ == "__main__":
    main()
