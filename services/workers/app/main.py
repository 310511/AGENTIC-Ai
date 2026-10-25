"""
Workers Service — RabbitMQ consumer (Phase 6).

Consumes task jobs from the `agent.tasks` queue, delegates execution
to the orchestrator, and handles retries with linear backoff.

Retry policy:
  - Up to settings.max_retries attempts per message.
  - Attempt header is incremented and the message is re-queued with a
    delay (asyncio.sleep) before each retry.
  - After max_retries the message is nack'd without requeue, routing it
    to the dead-letter queue (agent.tasks.dlq) automatically.

Idempotency:
  - task_id is used as the idempotency key. The runner checks current
    task status before starting — already-terminal tasks are acked
    immediately without re-running.

Usage:
  python -m app.main           (runs forever)
  python -m app.main --once    (process one message and exit — for testing)
"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys

import aio_pika
from sqlalchemy.ext.asyncio import async_sessionmaker

from .config import get_settings
from .db import make_engine, set_task_status
from .queue import declare_queues
from .runner import _TERMINAL, run_task

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


async def _process_message(
    message: aio_pika.abc.AbstractIncomingMessage,
    settings,
    session_factory: async_sessionmaker,
) -> None:
    """Handle one message: run with retries, ack on success, nack to DLQ on exhaustion."""
    async with message.process(requeue=False):  # manual ack inside context
        try:
            payload = json.loads(message.body)
        except json.JSONDecodeError:
            logger.error("Bad message body, sending to DLQ: %r", message.body[:200])
            await message.nack(requeue=False)
            return

        task_id = payload.get("task_id", "unknown")
        headers = dict(message.headers or {})
        attempt = int(headers.get("x-attempt", 1))

        logger.info("Received task_id=%s attempt=%d", task_id, attempt)

        # Idempotency: skip already-terminal tasks.
        # (Orchestrator may have completed it before this worker picked it up.)
        # We skip the DB check here and let runner.run_task handle the in_progress
        # set — the DB update is idempotent for non-terminal → in_progress transitions.

        success = await run_task(payload, settings, session_factory, attempt=attempt)

        if success:
            logger.info("Task %s succeeded on attempt %d", task_id, attempt)
            # message is acked by the process() context manager
            return

        # Failed — retry or dead-letter.
        if attempt < settings.max_retries:
            delay = attempt * settings.retry_delay_seconds
            logger.warning(
                "Task %s failed attempt %d/%d, retrying in %ds",
                task_id, attempt, settings.max_retries, delay,
            )
            await asyncio.sleep(delay)

            # Re-publish with incremented attempt header.
            channel = message.channel
            await channel.default_exchange.publish(
                aio_pika.Message(
                    body=message.body,
                    headers={**headers, "x-attempt": attempt + 1},
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                ),
                routing_key=settings.task_queue,
            )
        else:
            logger.error(
                "Task %s exhausted %d retries — sending to DLQ",
                task_id, settings.max_retries,
            )
            await set_task_status(
                session_factory, task_id, "failed",
                error_message=f"Exhausted {settings.max_retries} worker retries",
            )
            # nack without requeue → DLX routes to DLQ
            await message.nack(requeue=False)


async def run_consumer(once: bool = False) -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    logger.info(
        "Connecting to RabbitMQ: %s",
        settings.rabbitmq_url.split("@")[-1],  # hide credentials in log
    )
    connection = await aio_pika.connect_robust(
        settings.rabbitmq_url,
        reconnect_interval=5,
    )

    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=settings.prefetch_count)
        await declare_queues(channel, settings)

        queue = await channel.get_queue(settings.task_queue)

        logger.info(
            "Worker ready — queue=%s prefetch=%d max_retries=%d",
            settings.task_queue, settings.prefetch_count, settings.max_retries,
        )

        if once:
            # Consume exactly one message (useful for tests / smoke checks).
            async with queue.iterator() as q:
                async for message in q:
                    await _process_message(message, settings, session_factory)
                    break
        else:
            # Consume indefinitely; stop on SIGINT/SIGTERM.
            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            async with queue.iterator() as q:
                async for message in q:
                    if stop_event.is_set():
                        break
                    asyncio.create_task(
                        _process_message(message, settings, session_factory)
                    )

    await engine.dispose()
    logger.info("Worker shut down cleanly")


def main() -> None:
    once = "--once" in sys.argv
    asyncio.run(run_consumer(once=once))


if __name__ == "__main__":
    main()
