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
| `RCA_API_KEYS` | *(empty)* | JSON object mapping API key → `tenant_id`, e.g. `{"sk_live_xxx":"org_123"}`. When set, clients must send **`Authorization: Bearer <key>`** or **`X-API-Key`**; **`X-Tenant-ID` is not used for auth** (body `tenant_id` must still match the resolved tenant). When empty, local/dev behavior uses **`X-Tenant-ID`** only. |

For local async testing, use `export RCA_INGEST_SYNC=0` (or unset), post a trace, then `GET` it (may need a short delay while worker drains backlog).

- OpenAPI: http://127.0.0.1:8000/docs  
- Ingest: `POST /v1/traces` with auth as above; JSON `tenant_id` must match the authenticated tenant (**201** if sync ingest, **202** if queued)  
- Batch ingest: `POST /v1/traces/batch` with body `{ "traces": [...] }` and the same auth headers  
  - **201** when all items are synchronously accepted, **202** when all are queued, **207** for mixed outcomes  
  - SDK-friendly item fields: `status`, `http_status`, optional `error_code`, optional `detail`
- List: `GET /v1/traces?limit=&offset=&status=&started_at_from=&started_at_to=` — optional **inclusive** time bounds on **`started_at`** (run time), ISO-8601; omit both for no time filter  
- Fetch: `GET /v1/traces/{trace_id}` with the same auth  
- Diagnosis (rules v1): `GET /v1/traces/{trace_id}/diagnosis` — primary hypothesis, confidence, evidence (written when the trace is stored)

## Tests

```bash
cd backend
export PYTHONPATH=.
pytest -v
```

## Next implementation steps (see `plan.md`)

1. **Composite uniqueness** — DB constraint on `(tenant_id, trace_id)` across `traces`, `diagnoses`, `ingest_jobs`.  
2. **External durable queue** (SQS / Redis) + multi-worker scaling; keep DB backlog as local fallback.  
3. **Postgres** + object storage for blobs; keep SQLite for tests.  
4. **LLM explainer** (optional) over structured `Diagnosis` + more rules / tunable thresholds.
