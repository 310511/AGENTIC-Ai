# Workers Service

**Status:** Placeholder — Phase 6

## Responsibility

Python workers that consume jobs from **RabbitMQ** and execute long-running
agent tasks asynchronously. Supports retries with backoff, timeouts,
idempotency keys, dead-letter handling, and durable task-state checkpoints.

## Planned components

```
workers/
├── app/
│   ├── main.py              # Worker process entry point
│   ├── config.py
│   ├── consumer.py          # RabbitMQ consumer + message dispatch
│   ├── handlers/
│   │   └── task_handler.py  # Execute a single task job
│   ├── retry.py             # Backoff, idempotency, dead-letter policy
│   └── checkpoint.py        # Durable task state persistence
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Propagate the trusted user/tenant authorization context into jobs; do not
  accept arbitrary client-supplied identity as trusted.
- Support retries with exponential backoff, timeouts, and dead-letter queues.
- Persist durable checkpoints so work can recover after process failure.
- Use idempotency keys to handle duplicate message delivery safely.
- Avoid logging secrets or unnecessary personal data.
- Do not retry irreversible actions blindly — use bounded retry counts.

## Phase 6 dependencies

- `aio-pika` (async RabbitMQ client)
- `pydantic==2.7.1`
- `pydantic-settings==2.2.1`
- `httpx==0.27.0`
- `opentelemetry-api==1.24.0`
