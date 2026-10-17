"""
Knowledge Service — entry point (Phase 3 placeholder).

Will expose internal endpoints for document ingestion and vector retrieval
once BGE + FAISS + spaCy are implemented in Phase 3.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Knowledge service is a Phase 3 placeholder — "
        "no embedding or retrieval pipeline has been implemented yet."
    )


if __name__ == "__main__":
    main()
