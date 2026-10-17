# Orchestrator Service

**Status:** Placeholder — Phase 2

## Responsibility

Implements the stateful agent workflow using **LangGraph**. Receives tasks
from the API, plans execution steps, calls the LLM Gateway, retrieves context
from the Knowledge Service and Graph Memory, invokes tools via the MCP Client
Manager, and persists task state and checkpoints.

## Planned components

```
orchestrator/
├── app/
│   ├── main.py          # Service entry point / FastAPI app (internal)
│   ├── config.py        # Typed settings
│   ├── graph/
│   │   ├── state.py     # LangGraph state definition
│   │   ├── nodes.py     # Individual graph nodes (plan, retrieve, act, verify)
│   │   └── workflow.py  # Graph assembly and compilation
│   ├── llm/
│   │   └── gateway.py   # LLM Gateway — provider-neutral LLM calls
│   └── checkpoints.py   # Task state persistence / recovery
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Use explicit stop conditions, bounded loops, timeouts, and retry policies.
- Route long-running operations to the Execution Service; don't hold an HTTP
  request open indefinitely.
- Treat all LLM output as untrusted — validate structured output before acting.
- Never let generated text bypass the Policy Service or call tools outside the
  authorised set.

## Phase 2 dependencies

- `langgraph`
- `langchain-core`
- `httpx` (inter-service calls)
- `opentelemetry-*`
