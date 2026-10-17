# Graph Memory Service

**Status:** Placeholder — Phase 4

## Responsibility

Manages the Neo4j graph database: stores entities, relationships, and
historical facts with provenance links. Provides tenant-aware graph queries
to the Orchestrator for context retrieval.

## Planned components

```
graph-memory/
├── app/
│   ├── main.py              # Internal FastAPI app
│   ├── config.py
│   ├── neo4j_client.py      # Async Neo4j driver wrapper
│   ├── schema.py            # Node/relationship type definitions
│   ├── repositories/
│   │   ├── entity.py        # CRUD for entity nodes
│   │   └── relationship.py  # CRUD for relationship edges
│   └── queries/
│       └── retrieval.py     # Tenant-scoped graph retrieval queries
├── requirements.txt
└── Dockerfile
```

## Key design rules (from context.md)

- Define a versioned graph schema; document entity and relationship types.
- Support tenant isolation in graph queries; enforce it in the service layer.
- Make graph writes idempotent to avoid duplicates during retries.
- Avoid writing speculative LLM-generated relationships as verified facts
  without validation.
- Provenance (source, timestamp, confidence) must be stored with every fact.

## Phase 4 dependencies

- `neo4j` (official async Python driver)
- `pydantic==2.7.1`
- `pydantic-settings==2.2.1`
- `httpx==0.27.0`
