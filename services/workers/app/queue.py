"""
RabbitMQ queue setup helpers.

Declares the main task queue with a dead-letter exchange so messages
that exhaust retries are routed to the DLQ instead of being dropped.

Queue topology:
  agent.tasks      — main work queue (DLX → agent.tasks.dlq)
  agent.tasks.dlq  — dead-letter queue for failed/expired messages
"""
from __future__ import annotations

import logging

import aio_pika

logger = logging.getLogger(__name__)

MAIN_EXCHANGE   = ""           # default exchange (direct routing)
DLX_EXCHANGE    = "agent.dlx"  # dead-letter exchange name


async def declare_queues(channel: aio_pika.abc.AbstractChannel, settings) -> None:
    """Declare all queues and the DLX. Idempotent — safe to call on reconnect."""
    # Dead-letter exchange (fanout — only the DLQ is bound to it)
    dlx = await channel.declare_exchange(DLX_EXCHANGE, aio_pika.ExchangeType.DIRECT, durable=True)

    # Dead-letter queue — no further routing, just accumulates failed messages.
    dlq = await channel.declare_queue(settings.dead_letter_queue, durable=True)
    await dlq.bind(dlx, routing_key=settings.dead_letter_queue)

    # Main work queue — rejected messages go to the DLX.
    await channel.declare_queue(
        settings.task_queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange":    DLX_EXCHANGE,
            "x-dead-letter-routing-key": settings.dead_letter_queue,
        },
    )
    logger.info("Queues declared: %s → DLX → %s", settings.task_queue, settings.dead_letter_queue)
