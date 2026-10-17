#!/usr/bin/env zsh
# ============================================================
# Local dev startup — runs api + orchestrator natively (no Docker)
#
# Prerequisites (one-time):
#   brew install postgresql@16
#   brew services start postgresql@16
#   createuser -s postgres 2>/dev/null || true
#   createdb -U postgres agent_platform 2>/dev/null || true
#   psql -U postgres agent_platform < infra/postgres/init/01_schema.sql
#   ollama pull llama3.2
#
# Usage:
#   ./dev.sh          # start both services
#   ./dev.sh stop     # kill both services
# ============================================================

set -euo pipefail

API_DIR="services/api"
ORC_DIR="services/orchestrator"
LOG_DIR=".dev-logs"
API_PID_FILE="$LOG_DIR/api.pid"
ORC_PID_FILE="$LOG_DIR/orchestrator.pid"

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
  if [[ ! -d "$dir/.venv" ]]; then
    echo "→ Creating venv in $dir"
    python3 -m venv "$dir/.venv"
    "$dir/.venv/bin/pip" install -q --upgrade pip
    "$dir/.venv/bin/pip" install -q -r "$dir/requirements.txt"
  fi
}

stop_services() {
  for pidfile in "$API_PID_FILE" "$ORC_PID_FILE"; do
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

# Export .env into the current shell so both services inherit it.
set -a
# shellcheck disable=SC1091
source .env
set +a

echo "→ Starting orchestrator on :8001"
(
  cd "$ORC_DIR"
  .venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 --port 8001 \
    --reload \
    >> "../../$LOG_DIR/orchestrator.log" 2>&1 &
  echo $! > "../../$ORC_PID_FILE"
)

# Give orchestrator a moment before API starts firing requests at it.
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
echo "  API          → http://localhost:8000"
echo "  Orchestrator → http://localhost:8001"
echo "  API docs     → http://localhost:8000/docs"
echo ""
echo "Logs:  tail -f $LOG_DIR/api.log $LOG_DIR/orchestrator.log"
echo "Stop:  ./dev.sh stop"
