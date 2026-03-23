# Backend (Python)

Phase **A/B (initial)**: canonical trace schema (Pydantic), ingest + get-by-id APIs, SQLite persistence for local dev (Postgres in production later).

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

- OpenAPI: http://127.0.0.1:8000/docs  
- Ingest: `POST /v1/traces` with header `X-Tenant-ID` matching `tenant_id` in the JSON body  
- Fetch: `GET /v1/traces/{trace_id}` with the same `X-Tenant-ID`

## Tests

```bash
cd backend
export PYTHONPATH=.
pytest -v
```

## Next implementation steps (see `plan.md`)

1. **Queue** between ingest accept and normalization (SQS / Redis / in-proc for dev).  
2. **List / filter traces** (`GET /v1/traces`) with pagination.  
3. **Postgres** + object storage for blobs; keep SQLite for tests.  
4. **API keys / auth** beyond `X-Tenant-ID`.  
5. **Diagnosis engine** + `DiagnosisRecord` storage.
