# AI Agent Platform

An end-to-end, modular AI agent platform using a microservices-oriented architecture.

## Architecture overview

```
User / Browser
    │
    ▼
Next.js + TypeScript UI
    │
    ▼
Supabase Auth (identity and JWT)
    │
    ▼
FastAPI API (JWT validation, RBAC, tenant isolation)
    │
    ▼
Agent Orchestrator (LangGraph)
  ├── LLM Gateway (Ollama)
  ├── Knowledge Service (BGE + FAISS + spaCy)
  ├── Graph Memory (Neo4j)
  └── MCP Client Manager
    │
    ▼
Policy / Approval checks
    │
    ▼
Execution Service → RabbitMQ → Python workers
```

## Repository layout

```
/
├── apps/
│   └── web/                     # Next.js frontend (Phase 2)
├── services/
│   ├── api/                     # FastAPI entry point and routes
│   ├── orchestrator/            # LangGraph workflows (Phase 2)
│   ├── knowledge/               # Embeddings, FAISS, spaCy (Phase 3)
│   ├── graph-memory/            # Neo4j access (Phase 4)
│   ├── mcp-client-manager/      # MCP connections (Phase 5)
│   ├── policy/                  # Authorization and approval
│   └── workers/                 # RabbitMQ consumers (Phase 6)
├── mcp-servers/
│   ├── research/
│   ├── data/
│   └── workflow/
├── packages/
│   ├── contracts/               # Shared Pydantic schemas
│   └── auth/                    # Shared JWT/tenant helpers
├── infra/
│   ├── docker-compose.yml
│   └── observability/
├── tests/
│   ├── integration/
│   └── security/
├── .env.example
└── context.md
```

## Getting started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node.js 20+ (for frontend, Phase 2)
- A Supabase project (free tier works for development)

### 1. Clone and configure

```bash
git clone <repo-url>
cd ai-agent-platform
cp .env.example .env
# Edit .env with your real Supabase credentials and secrets
```

### 2. Start infrastructure

```bash
docker compose -f infra/docker-compose.yml up -d
```

This starts: PostgreSQL (via Supabase local or remote), Redis, Neo4j, RabbitMQ, and the API service.

### 3. Install API dependencies

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Run the API locally (without Docker)

```bash
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Check health

```bash
curl http://localhost:8000/health
```

## Implementation phases

| Phase | Status | Focus |
|-------|--------|-------|
| 1 | ✅ In progress | Secure foundation — API, auth, infra |
| 2 | 🔲 Planned | Agent core — LangGraph + LLM Gateway |
| 3 | 🔲 Planned | Knowledge retrieval — BGE + FAISS + spaCy |
| 4 | 🔲 Planned | Graph memory — Neo4j |
| 5 | 🔲 Planned | MCP integrations |
| 6 | 🔲 Planned | Durable execution — RabbitMQ workers |
| 7 | 🔲 Planned | Production hardening |

## Security

- All protected API endpoints require a valid Supabase JWT.
- RBAC and PostgreSQL RLS enforce role and tenant isolation.
- Never commit `.env` or any file containing real secrets.
- See `context.md` Section 6 for the full security requirements.

## Contributing

Read `context.md` before making architecture changes. Preserve the selected stack and decisions unless there is a concrete reason to change them.
