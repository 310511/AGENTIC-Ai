# AI Agent Platform

An end-to-end modular AI agent platform. Authenticated users submit tasks in plain English; a LangGraph-based agent plans steps, calls tools, executes, and persists results.

## What it does today

**One proven capability: Research & Summarize**

Submit a task like "Research X and summarize it" → the agent:
1. Searches Wikipedia via the research MCP server
2. Fetches the article content
3. Synthesizes a clean summary using a local LLM (Ollama)
4. Persists the result to Postgres — visible in the UI

This is a complete agentic loop: auth → queue → plan → tool use → execute → result.

## Architecture

```
Browser (Next.js :3000)
    ↓  Supabase JWT
FastAPI API (:8000)
    ↓  RabbitMQ queue
Workers consumer
    ↓  HTTP
Orchestrator (:8001)  ←→  LangGraph workflow
    ├── Knowledge Service (:8002)  — FAISS vector search
    ├── Graph Memory (:8003)       — Neo4j entities
    └── MCP Client Manager (:8004) — research server tools
            └── research/web_search    (Wikipedia)
            └── research/fetch_url     (any HTTPS URL)
            └── research/summarise_text
```

## Services

| Port | Service | Status |
|------|---------|--------|
| 3000 | Next.js UI | ✅ |
| 8000 | FastAPI API | ✅ |
| 8001 | Orchestrator (LangGraph) | ✅ |
| 8002 | Knowledge (FAISS + spaCy) | ✅ |
| 8003 | Graph Memory (Neo4j) | ✅ |
| 8004 | MCP Client Manager | ✅ |
| — | RabbitMQ workers | ✅ |

## Start everything

```zsh
# Prerequisites (one-time)
brew services start postgresql@16
brew services start neo4j
brew services start rabbitmq
ollama serve  # runs automatically on macOS

# Start all backend services
/tmp/start_services.sh   # or recreate from dev.sh

# Start frontend
cd apps/web && npm run dev
```

Open http://localhost:3000 — sign in with Supabase, submit a task.

## Environment

Copy `.env.example` → `.env`. Key values already set for local dev:
- `DEFAULT_LLM_MODEL=qwen2.5-coder:3b` (fast local inference)
- `MCP_SERVERS` — research server wired in
- `NEO4J_PASSWORD`, `DATABASE_URL` — local Postgres + Neo4j

## Phases completed

| Phase | Done |
|-------|------|
| 1 — Auth, API, infra | ✅ |
| 2 — LangGraph orchestrator + LLM gateway | ✅ |
| 3 — Knowledge service (FAISS + embeddings) | ✅ |
| 4 — Graph memory (Neo4j) | ✅ |
| 5 — MCP tool integration | ✅ |
| 6 — RabbitMQ durable workers | ✅ |
| Frontend (Next.js) | ✅ |
| 7 — Production hardening | 🔲 |

## Intended use

This platform is designed as a **component** in a larger AI agent system — not a general-purpose chatbot. It handles one thing well (research + summarize) and is built to extend: add MCP servers to add capabilities, ingest documents to give the agent domain knowledge, configure tools per tenant.
