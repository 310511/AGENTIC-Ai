"""
Workers Service — entry point (Phase 6 placeholder).

Will consume jobs from RabbitMQ and execute long-running agent tasks with
retries, idempotency, and durable checkpointing once implemented in Phase 6.
"""
from __future__ import annotations

import logging
import sys

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info(
        "Workers service is a Phase 6 placeholder — "
        "no RabbitMQ consumer has been implemented yet."
    )


if __name__ == "__main__":
    main()
