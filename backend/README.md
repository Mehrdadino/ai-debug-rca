# Backend (Python)

Phase **A/B + diagnosis (v0.4)**: canonical traces, **async ingest with DB-backed durable backlog** (`ingest_jobs` table), **list traces**, **rule-based diagnosis**, SQLite for local dev.

## Requirements

- Python **3.9+** (3.11+ recommended)
- Dependencies from `pyproject.toml`

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.10" "pydantic-settings>=2.6" "sqlalchemy[asyncio]>=2.0.36" "aiosqlite>=0.20"
pip install "httpx>=0.27" "pytest>=8.3" "pytest-asyncio>=0.24"  # dev
```

If `pip install -e .` fails (older pip), keep `PYTHONPATH=.` as below.

## Run the API

```bash
cd backend
export PYTHONPATH=.
export RCA_DATABASE_URL="sqlite+aiosqlite:///./data/app.db"
mkdir -p data
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Use **`python3 -m uvicorn`** so the same interpreter that has FastAPI/uvicorn is used. The bare `uvicorn` command only works if that interpreter’s `bin` directory is on your `PATH` (e.g. after `source .venv/bin/activate`).

### Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `RCA_DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` | Async SQLAlchemy URL |
| `RCA_INGEST_SYNC` | `0` (false) | If `1` / `true`, `POST /v1/traces` writes in the request and returns **201**. If false, traces are first persisted to the `ingest_jobs` backlog and API returns **202**; worker drains backlog to `traces`. |
| `RCA_INGEST_QUEUE_MAXSIZE` | `10000` | Max backlog row count (`ingest_jobs`) before API returns **503** |
| `RCA_INGEST_BATCH_MAX_SIZE` | `100` | Max items accepted by `POST /v1/traces/batch` |
| `RCA_INGEST_RATE_LIMIT_RPS` | `0` (disabled) | Per-tenant ingest request limit (requests/second). When exceeded, API returns **429** with `Retry-After`. |
| `RCA_INGEST_DAILY_TRACE_QUOTA` | `0` (disabled) | Per-tenant ingest quota (trace count/day UTC). Applied to single and batch ingest. Exceeding returns **429** with `Retry-After`. |
| `RCA_API_KEYS` | *(empty)* | JSON object mapping API key → `tenant_id`, e.g. `{"sk_live_xxx":"org_123"}`. When set, clients must send **`Authorization: Bearer <key>`** or **`X-API-Key`**; **`X-Tenant-ID` is not used for auth** (body `tenant_id` must still match the resolved tenant). When empty, local/dev behavior uses **`X-Tenant-ID`** only. |
| `RCA_ADMIN_TOKEN` | *(empty / disabled)* | Enables admin APIs for per-tenant limits via `X-Admin-Token`. |

For local async testing, use `export RCA_INGEST_SYNC=0` (or unset), post a trace, then `GET` it (may need a short delay while worker drains backlog).

- OpenAPI: http://127.0.0.1:8000/docs  
- Ingest: `POST /v1/traces` with auth as above; JSON `tenant_id` must match the authenticated tenant (**201** if sync ingest, **202** if queued)  
- Batch ingest: `POST /v1/traces/batch` with body `{ "traces": [...] }` and the same auth headers  
  - **201** when all items are synchronously accepted, **202** when all are queued, **207** for mixed outcomes  
  - SDK-friendly item fields: `status`, `http_status`, optional `error_code`, optional `detail`
- Rate/quota failures return **429** with `Retry-After` and a retry hint in `detail`.
- List: `GET /v1/traces?limit=&offset=&status=&environment=&started_at_from=&started_at_to=` — optional filters; time bounds are **inclusive** on **`started_at`** (run time), ISO-8601  
- Fetch: `GET /v1/traces/{trace_id}?environment=prod|staging|dev|critical` (defaults to `prod`)  
- Diagnosis (rules v1): `GET /v1/traces/{trace_id}/diagnosis?environment=...` (defaults to `prod`) — primary hypothesis, confidence, evidence
- Admin limits (when `RCA_ADMIN_TOKEN` is set):
  - `GET /v1/admin/tenants/{tenant_id}/limits`
  - `PUT /v1/admin/tenants/{tenant_id}/limits` with `{ "ingest_rate_limit_rps": int>=0, "ingest_daily_trace_quota": int>=0 }`

## Tests

```bash
cd backend
export PYTHONPATH=.
pytest -v
```

After **SQLAlchemy model / constraint changes**, remove the local DB file once so `create_all` builds fresh tables (e.g. `rm -f data/pytest.db data/app.db` from `backend/`).

## Data model notes

- **`UNIQUE (tenant_id, environment, trace_id)`** on `traces`, `diagnoses`, and `ingest_jobs` — same UUID may exist under different tenants or environments; **409** if the triple collides for the authenticated tenant.
- Environment is a first-class dimension: `prod|staging|dev|critical` (default `prod`).
- Current rate limiter is **in-process** (per API process). For multi-instance deployments, move rate/quota state to shared storage (e.g. Redis/Postgres).
- Per-tenant policy overrides are persisted in `tenant_limits` and applied before global defaults.

## Next implementation steps (see `plan.md` §19)

1. **PostgreSQL** + object storage when moving off single-file SQLite for staging/prod.  
2. **Alembic** (or equivalent) for schema evolution.  
3. **Distributed rate-limiter backend** (Redis/Postgres counters) for multi-instance API nodes.  
4. **Python SDK**, **Web UI**, **LLM explainer** — as in `plan.md`.
