"""
RabbitMQ publisher for the API service.

Tasks are published to the agent.tasks queue so the workers service
picks them up durably. The orchestrator is still reachable directly
for status queries.

The connection is opened once at startup and reused across requests.
aio_pika.connect_robust handles reconnects automatically.
"""
from __future__ import annotations

import json
import logging

import aio_pika

logger = logging.getLogger(__name__)

TASK_QUEUE = "agent.tasks"

_connection: aio_pika.abc.AbstractRobustConnection | None = None


async def connect(rabbitmq_url: str) -> None:
    global _connection
    _connection = await aio_pika.connect_robust(
        rabbitmq_url, reconnect_interval=5
    )
    # Ensure the queue exists with the same DLX args the workers use.
    async with _connection.channel() as ch:
        await ch.declare_exchange("agent.dlx", aio_pika.ExchangeType.DIRECT, durable=True)
        dlq = await ch.declare_queue("agent.tasks.dlq", durable=True)
        await dlq.bind(await ch.get_exchange("agent.dlx"), routing_key="agent.tasks.dlq")
        await ch.declare_queue(
            TASK_QUEUE,
            durable=True,
            arguments={
                "x-dead-letter-exchange":    "agent.dlx",
                "x-dead-letter-routing-key": "agent.tasks.dlq",
            },
        )
    logger.info("RabbitMQ publisher connected")


async def close() -> None:
    global _connection
    if _connection and not _connection.is_closed:
        await _connection.close()
    _connection = None


async def publish_task(
    task_id: str,
    tenant_id: str,
    title: str,
    description: str,
) -> bool:
    """
    Publish a task job to the queue. Returns True on success.

    Non-fatal: logs and returns False if RabbitMQ is unavailable so the
    caller can fall back to a direct orchestrator call.
    """
    if _connection is None or _connection.is_closed:
        logger.warning("RabbitMQ not connected — skipping queue publish for task %s", task_id)
        return False
    try:
        async with _connection.channel() as channel:
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps({
                        "task_id":     task_id,
                        "tenant_id":   tenant_id,
                        "title":       title,
                        "description": description,
                    }).encode(),
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    headers={"x-attempt": 1},
                ),
                routing_key=TASK_QUEUE,
            )
        logger.debug("Published task %s to queue", task_id)
        return True
    except Exception as exc:
        logger.error("Failed to publish task %s: %s", task_id, exc)
        return False
