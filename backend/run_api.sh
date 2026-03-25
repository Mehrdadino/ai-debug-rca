#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PYTHONPATH="${PYTHONPATH:-.}"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
LOG_LEVEL="${LOG_LEVEL:-info}"
LOOP_IMPL="${LOOP_IMPL:-asyncio}"

DEFAULT_PG_URL="postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca"
export RCA_DATABASE_URL="${RCA_DATABASE_URL:-$DEFAULT_PG_URL}"

# Common local misconfig guard: stale :5432 URL points to system Postgres
# (often missing the expected rca role/db). Default local stack is :5433.
if [[ "${RCA_DATABASE_URL}" == *127.0.0.1:5432* ]] || [[ "${RCA_DATABASE_URL}" == *localhost:5432* ]]; then
  if [[ "${RCA_ALLOW_LOCAL_5432:-0}" != "1" ]]; then
    echo "Detected local RCA_DATABASE_URL on port 5432; switching to local Docker Postgres on 5433."
    echo "Set RCA_ALLOW_LOCAL_5432=1 to keep using port 5432 explicitly."
    export RCA_DATABASE_URL="${DEFAULT_PG_URL}"
  fi
fi

echo "Starting API on ${HOST}:${PORT}"

EXISTING_PIDS="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "${EXISTING_PIDS}" ]]; then
  echo "Stopping stale listener(s) on port ${PORT}: ${EXISTING_PIDS}"
  kill ${EXISTING_PIDS} || true
  sleep 0.5
fi

COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.postgres.yml"
LOCAL_PG_PATTERN=0
if [[ "${RCA_DATABASE_URL}" == *127.0.0.1:5433* ]] || [[ "${RCA_DATABASE_URL}" == *localhost:5433* ]]; then
  LOCAL_PG_PATTERN=1
fi

if [[ "${LOCAL_PG_PATTERN}" == "1" ]] && [[ "${RCA_SKIP_DOCKER_POSTGRES:-0}" != "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required to run the local PostgreSQL container (port 5433)."
    echo "Install Docker, or point RCA_DATABASE_URL at a reachable Postgres and set RCA_SKIP_DOCKER_POSTGRES=1."
    exit 1
  fi
  echo "Ensuring PostgreSQL (docker compose)..."
  docker compose -f "${COMPOSE_FILE}" up -d
  READY=0
  for _ in $(seq 1 60); do
    if docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U rca -d rca >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 1
  done
  if [[ "${READY}" != "1" ]]; then
    echo "Postgres did not become ready in time."
    exit 1
  fi
  if [[ "$(docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U rca -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname='rca_test'" 2>/dev/null || true)" != "1" ]]; then
    docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U rca -d postgres -c "CREATE DATABASE rca_test"
  fi
  echo "DB: ${RCA_DATABASE_URL}"
else
  echo "DB: ${RCA_DATABASE_URL}"
fi

echo "Running migrations..."
python3 -m alembic upgrade head

exec python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" --log-level "${LOG_LEVEL}" --loop "${LOOP_IMPL}"
