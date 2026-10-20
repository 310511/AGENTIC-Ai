#!/usr/bin/env zsh
# ============================================================
# Local dev startup — runs api + orchestrator + knowledge + graph-memory + mcp-client-manager natively
#
# Prerequisites (one-time):
#   brew install postgresql@16 && brew services start postgresql@16
#   createuser -s postgres 2>/dev/null || true
#   createdb -U postgres agent_platform
#   psql -U postgres agent_platform < infra/postgres/init/01_schema.sql
#   psql -U postgres agent_platform < infra/postgres/init/02_knowledge.sql
#   ollama pull llama3.2
#
#   Neo4j (Phase 4):
#   brew install neo4j && brew services start neo4j
#   cypher-shell -u neo4j -p <password> < infra/neo4j/init/01_constraints.cypher
#
#   MCP research server (Phase 5) — install into mcp-client-manager venv after first run:
#   services/mcp-client-manager/.venv/bin/pip install -q -r mcp-servers/research/requirements.txt
#
# After first knowledge venv install, also run:
#   services/knowledge/.venv/bin/python -m spacy download en_core_web_sm
#
# Usage:
#   ./dev.sh          # start all services
#   ./dev.sh stop     # kill all services
# ============================================================

set -euo pipefail

API_DIR="services/api"
ORC_DIR="services/orchestrator"
KNO_DIR="services/knowledge"
GRM_DIR="services/graph-memory"
MCP_DIR="services/mcp-client-manager"
LOG_DIR=".dev-logs"
API_PID_FILE="$LOG_DIR/api.pid"
ORC_PID_FILE="$LOG_DIR/orchestrator.pid"
KNO_PID_FILE="$LOG_DIR/knowledge.pid"
GRM_PID_FILE="$LOG_DIR/graph-memory.pid"
MCP_PID_FILE="$LOG_DIR/mcp-client-manager.pid"

# ── helpers ──────────────────────────────────────────────────

die() { echo "ERROR: $*" >&2; exit 1; }

check_postgres() {
  pg_isready -U postgres -d agent_platform -q 2>/dev/null \
    || die "PostgreSQL not ready. Run: brew services start postgresql@16"
}

check_ollama() {
  curl -sf http://localhost:11434 >/dev/null 2>&1 \
    || die "Ollama not running. Run: ollama serve  (or it starts automatically on macOS)"
}

setup_venv() {
  local dir=$1
  local py=${2:-python3}   # caller can pass a specific interpreter
  if [[ ! -d "$dir/.venv" ]]; then
    echo "→ Creating venv in $dir ($(${py} --version 2>&1))"
    "$py" -m venv "$dir/.venv"
    "$dir/.venv/bin/pip" install -q --upgrade pip
    "$dir/.venv/bin/pip" install -q -r "$dir/requirements.txt"
  fi
}

stop_services() {
  for pidfile in "$API_PID_FILE" "$ORC_PID_FILE" "$KNO_PID_FILE" "$GRM_PID_FILE" "$MCP_PID_FILE"; do
    if [[ -f "$pidfile" ]]; then
      local pid
      pid=$(cat "$pidfile")
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" && echo "Stopped pid $pid"
      fi
      rm -f "$pidfile"
    fi
  done
  echo "Services stopped."
  exit 0
}

# ── stop mode ────────────────────────────────────────────────

[[ "${1:-}" == "stop" ]] && stop_services

# ── start mode ───────────────────────────────────────────────

mkdir -p "$LOG_DIR"

check_postgres
check_ollama

setup_venv "$API_DIR"
setup_venv "$ORC_DIR"
# Knowledge service requires Python 3.12 — spaCy/sentence-transformers wheels
# are not yet available for Python 3.14.
setup_venv "$KNO_DIR" /opt/homebrew/bin/python3.12
setup_venv "$GRM_DIR"
setup_venv "$MCP_DIR"

# Warn if spaCy model is missing (non-fatal — knowledge service will error at runtime)
if ! "$KNO_DIR/.venv/bin/python" -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
  echo "WARN: spaCy model not found. Run: $KNO_DIR/.venv/bin/python -m spacy download en_core_web_sm"
fi

# Export .env into the current shell so all services inherit it.
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "→ Starting knowledge service on :8002"
(
  cd "$KNO_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8002 \
    --reload \
    >> "../../$LOG_DIR/knowledge.log" 2>&1 &
  echo $! > "../../$KNO_PID_FILE"
)

# Knowledge service takes time to load BGE model — give it a head start.
sleep 2

echo "→ Starting graph-memory service on :8003"
(
  cd "$GRM_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8003 \
    --reload \
    >> "../../$LOG_DIR/graph-memory.log" 2>&1 &
  echo $! > "../../$GRM_PID_FILE"
)

sleep 1

echo "→ Starting mcp-client-manager on :8004"
(
  cd "$MCP_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8004 \
    --reload \
    >> "../../$LOG_DIR/mcp-client-manager.log" 2>&1 &
  echo $! > "../../$MCP_PID_FILE"
)

sleep 1

echo "→ Starting orchestrator on :8001"
(
  cd "$ORC_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8001 \
    --reload \
    >> "../../$LOG_DIR/orchestrator.log" 2>&1 &
  echo $! > "../../$ORC_PID_FILE"
)

sleep 1

echo "→ Starting api on :8000"
(
  cd "$API_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --reload \
    >> "../../$LOG_DIR/api.log" 2>&1 &
  echo $! > "../../$API_PID_FILE"
)

echo ""
echo "Services running:"
echo "  API              → http://localhost:8000  (docs: /docs)"
echo "  Orchestrator     → http://localhost:8001"
echo "  Knowledge        → http://localhost:8002  (docs: /docs)"
echo "  Graph Memory     → http://localhost:8003  (docs: /docs)"
echo "  MCP Client Mgr   → http://localhost:8004  (docs: /docs)"
echo ""
echo "Logs:  tail -f $LOG_DIR/api.log $LOG_DIR/orchestrator.log $LOG_DIR/knowledge.log $LOG_DIR/graph-memory.log $LOG_DIR/mcp-client-manager.log"
echo "Stop:  ./dev.sh stop"
