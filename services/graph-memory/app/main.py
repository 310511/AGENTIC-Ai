"""
Graph Memory Service — entry point (Phase 4 placeholder).

Will expose internal endpoints for entity/relationship storage and
graph-based context retrieval once Neo4j integration is implemented in Phase 4.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Graph Memory service is a Phase 4 placeholder — "
        "no Neo4j integration has been implemented yet."
    )


if __name__ == "__main__":
    main()
