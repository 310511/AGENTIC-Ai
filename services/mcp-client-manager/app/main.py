"""
MCP Client Manager — entry point (Phase 5 placeholder).

Will manage connections to MCP servers, enforce tool allowlists and policy
checks, and provide a normalised tool-invocation interface to the Orchestrator.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "MCP Client Manager is a Phase 5 placeholder — "
        "no MCP server connections have been implemented yet."
    )


if __name__ == "__main__":
    main()
