#!/usr/bin/env bash
set -euo pipefail

# Use repo-local imports when package is not installed editable.
export PYTHONPATH="${PYTHONPATH:-.}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
LOG_LEVEL="${LOG_LEVEL:-info}"
LOOP_IMPL="${LOOP_IMPL:-asyncio}"
DEFAULT_SQLITE_URL="sqlite+aiosqlite:///./data/app.db"
AUTO_DB_FALLBACK="${AUTO_DB_FALLBACK:-1}"

echo "Starting API on ${HOST}:${PORT}"

# Clear stale listeners that can linger after interrupted dev sessions.
EXISTING_PIDS="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "${EXISTING_PIDS}" ]]; then
  echo "Stopping stale listener(s) on port ${PORT}: ${EXISTING_PIDS}"
  kill ${EXISTING_PIDS} || true
  sleep 0.5
fi

# Pick a DB URL that can actually boot right now:
# - no RCA_DATABASE_URL => local sqlite
# - postgres URL and reachable => keep it
# - postgres URL and not reachable => fallback to sqlite (unless AUTO_DB_FALLBACK=0)
if [[ -z "${RCA_DATABASE_URL:-}" ]]; then
  export RCA_DATABASE_URL="${DEFAULT_SQLITE_URL}"
  echo "DB: sqlite (default local)"
elif [[ "${RCA_DATABASE_URL}" == postgresql+asyncpg://* ]]; then
  if python3 - <<'PY'
import os
import sys
import psycopg

url = os.environ["RCA_DATABASE_URL"]
sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
try:
    conn = psycopg.connect(sync_url, connect_timeout=2)
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
PY
  then
    echo "DB: postgres (${RCA_DATABASE_URL})"
  else
    if [[ "${AUTO_DB_FALLBACK}" == "1" ]]; then
      echo "DB: postgres unavailable, falling back to sqlite local DB"
      export RCA_DATABASE_URL="${DEFAULT_SQLITE_URL}"
    else
      echo "DB: postgres unavailable and AUTO_DB_FALLBACK=0; refusing to start"
      exit 1
    fi
  fi
else
  echo "DB: ${RCA_DATABASE_URL}"
fi

exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" --loop "${LOOP_IMPL}"
