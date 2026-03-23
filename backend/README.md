# Backend (Python)

Phase **A/B + diagnosis (v0.3)**: canonical traces, **async ingest queue** (in-process), **list traces**, **rule-based diagnosis** (stored with each trace; `GET .../diagnosis`), SQLite for local dev.

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
| `RCA_INGEST_SYNC` | `0` (false) | If `1` / `true`, `POST /v1/traces` writes in the request and returns **201**. If false, traces are **queued** and the API returns **202** (worker persists in background). |
| `RCA_INGEST_QUEUE_MAXSIZE` | `10000` | When ingest is async, queue capacity before **503** |

For local curl testing of the async path, use `export RCA_INGEST_SYNC=0` (or unset), post a trace, then `GET` it (you may need a short delay before the worker flushes the queue on a loaded machine).

- OpenAPI: http://127.0.0.1:8000/docs  
- Ingest: `POST /v1/traces` with header `X-Tenant-ID` matching `tenant_id` in the JSON body (**201** if sync ingest, **202** if queued)  
- List: `GET /v1/traces?limit=&offset=&status=` with `X-Tenant-ID`  
- Fetch: `GET /v1/traces/{trace_id}` with the same `X-Tenant-ID`  
- Diagnosis (rules v1): `GET /v1/traces/{trace_id}/diagnosis` — primary hypothesis, confidence, evidence (written when the trace is stored)

## Tests

```bash
cd backend
export PYTHONPATH=.
pytest -v
```

## Next implementation steps (see `plan.md`)

1. **Durable queue** (SQS / Redis) before returning 202; keep in-proc for dev.  
2. **Postgres** + object storage for blobs; keep SQLite for tests.  
3. **API keys / auth** beyond `X-Tenant-ID`.  
4. **LLM explainer** (optional) over structured `Diagnosis` + more rules / tunable thresholds.
