"""
Orchestrator Service — FastAPI entry point.

Internal endpoints (not exposed to the public internet):
  POST /run              — start a task workflow (called by the API service)
  GET  /status/{task_id} — get current task status from DB

The orchestrator runs the LangGraph workflow in a background task so
/run returns immediately (202 Accepted) and the API can poll /status.
"""
from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .graph.workflow import build_workflow
from .graph_client import GraphClient
from .knowledge_client import KnowledgeClient
from .llm.gateway import LLMGateway
from .mcp_client import MCPClient

logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()

# ── DB engine (same Postgres as the API, used to update task status) ──────────
_db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://", 1) \
                                .replace("postgres://",    "postgresql+asyncpg://", 1)
_engine = create_async_engine(_db_url, pool_pre_ping=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)

# ── LLM + compiled workflow (built once at startup) ───────────────────────────
_llm: LLMGateway | None = None
_workflow = None
_knowledge: KnowledgeClient | None = None
_graph: GraphClient | None = None
_mcp: MCPClient | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _llm, _workflow, _knowledge, _graph, _mcp
    _llm = LLMGateway(settings)
    _knowledge = KnowledgeClient(settings)
    _graph = GraphClient(settings)
    _mcp = MCPClient(settings)
    _workflow = build_workflow(_llm, _mcp)
    logger.info(
        "Orchestrator ready — model=%s ollama=%s knowledge=%s graph=%s mcp=%s",
        settings.default_llm_model, settings.ollama_base_url,
        settings.knowledge_url, settings.graph_memory_url,
        settings.mcp_client_manager_url,
    )
    yield
    await _engine.dispose()
    await _knowledge.close()
    await _graph.close()
    await _mcp.close()


app = FastAPI(title="AI Agent Orchestrator", version="0.1.0",
              docs_url="/docs", lifespan=lifespan)


# ── Schemas ───────────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    task_id: str
    tenant_id: str
    title: str
    description: str


# ── Task status constants (mirror contracts.tasks.TaskStatus) ─────────────────
_STATUS_IN_PROGRESS = "in_progress"
_STATUS_COMPLETED   = "completed"
_STATUS_FAILED      = "failed"


# ── DB helpers ────────────────────────────────────────────────────────────────

async def _set_task_status(
    task_id: str,
    new_status: str,
    result: dict | None = None,
    error_message: str | None = None,
) -> None:
    """Write task status (and optional result/error) back to Postgres."""
    values: dict = {
        "status": new_status,
        "updated_at": datetime.now(tz=timezone.utc),
    }
    if result is not None:
        values["result"] = result
    if error_message is not None:
        values["error_message"] = error_message
    if new_status == _STATUS_COMPLETED:
        values["completed_at"] = datetime.now(tz=timezone.utc)

    async with _session_factory() as session:
        await session.execute(
            # Raw text update so the orchestrator doesn't need the ORM model.
            update_stmt(task_id, values)
        )
        await session.commit()


def update_stmt(task_id: str, values: dict):
    """Build a SQLAlchemy core update for the tasks table."""
    from sqlalchemy import text
    set_parts = ", ".join(f"{k} = :{k}" for k in values)
    return text(
        f"UPDATE tasks SET {set_parts} WHERE id = :task_id"
    ).bindparams(**values, task_id=task_id)


# ── Background workflow runner ────────────────────────────────────────────────

async def _run_workflow(req: RunRequest) -> None:
    """
    Execute the LangGraph workflow for a task.

    Runs as a FastAPI background task — never holds the HTTP response open.
    Updates task status in Postgres at start, completion, and failure.
    """
    task_id = req.task_id
    try:
        await _set_task_status(task_id, _STATUS_IN_PROGRESS)

        # Retrieve relevant context from the knowledge service before planning.
        # Non-fatal: empty string if knowledge service is unavailable.
        chunks = await _knowledge.retrieve(req.tenant_id, f"{req.title} {req.description}")
        context = "\n\n".join(
            f"[{c['document_id']} chunk {c['chunk_index']}] {c['text']}"
            for c in chunks
        ) if chunks else ""

        # Retrieve graph memory context (entities/relationships). Non-fatal.
        graph_context = await _graph.retrieve(
            req.tenant_id, f"{req.title} {req.description}"
        )

        initial_state = {
            "task_id":       task_id,
            "tenant_id":     req.tenant_id,
            "title":         req.title,
            "description":   req.description,
            "context":       context,
            "graph_context": graph_context,
            "retries":       0,
        }

        final_state = await _workflow.ainvoke(initial_state)  # type: ignore[union-attr]

        if final_state.get("error"):
            await _set_task_status(
                task_id, _STATUS_FAILED,
                error_message=final_state["error"],
            )
            logger.error("Task %s failed: %s", task_id, final_state["error"])
        else:
            await _set_task_status(
                task_id, _STATUS_COMPLETED,
                result={"output": final_state.get("result", "")},
            )
            logger.info("Task %s completed", task_id)
            # Persist the task title/description as a minimal entity so future
            # tasks can retrieve relevant historical context. Non-fatal.
            await _graph.store(
                req.tenant_id,
                entities=[{
                    "text": req.title,
                    "label": "TASK",
                    "source_document_id": task_id,
                    "metadata": {"description": req.description[:256]},
                }],
            )

    except Exception as exc:
        logger.exception("Unhandled error in workflow for task %s", task_id)
        await _set_task_status(task_id, _STATUS_FAILED, error_message=str(exc))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/status/{task_id}")
async def task_status(task_id: str):
    """Return current task status from Postgres."""
    try:
        uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task_id")
    from sqlalchemy import text as _text
    async with _session_factory() as session:
        row = (await session.execute(
            _text("SELECT id, status, result, error_message, updated_at FROM tasks WHERE id = :id"),
            {"id": task_id},
        )).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id":       str(row["id"]),
        "status":        row["status"],
        "result":        row["result"],
        "error_message": row["error_message"],
        "updated_at":    row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@app.post("/run", status_code=status.HTTP_202_ACCEPTED)
async def run_task(req: RunRequest, background_tasks: BackgroundTasks):
    """
    Kick off a task workflow. Returns 202 immediately.
    The workflow runs in the background and writes results to Postgres.
    """
    if _workflow is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")
    background_tasks.add_task(_run_workflow, req)
    return {"accepted": True, "task_id": req.task_id}


@app.get("/health")
async def health():
    return {"status": "ok"}
