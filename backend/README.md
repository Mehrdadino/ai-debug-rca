# Backend (Python)

Phase **A/B + diagnosis (v0.4)**: canonical traces, **async ingest with DB-backed durable backlog** (`ingest_jobs` table), **list traces**, **rule-based diagnosis**. **PostgreSQL** is required for local dev, tests, and production.

## Requirements

- Python **3.9+** (3.11+ recommended)
- Dependencies from `pyproject.toml`
- **Docker** (for `docker compose` and the local Postgres container on port **5433**), unless you point `RCA_DATABASE_URL` at another reachable Postgres and set `RCA_SKIP_DOCKER_POSTGRES=1`

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e ".[dev]"
```

Copy `../.env.example` to `.env` in this directory only if you need to override defaults. The process reads `.env` from the working directory (`backend/`). Do not commit `.env`.

If `pip install -e ".[dev]"` fails on an older pip, install the packages listed in `pyproject.toml` directly and keep `PYTHONPATH=.` when you start the API.

## Run the API

**Recommended:** use `./run_api.sh` from `backend/`. It starts the Postgres container (`docker-compose.postgres.yml`), waits until the DB is ready, creates the `rca_test` database if missing (for pytest), runs `alembic upgrade head`, then starts uvicorn. You do not need a separate manual `docker compose up` before each session.

```bash
cd backend
./run_api.sh
```

Optional overrides:

```bash
HOST=127.0.0.1 PORT=8000 LOG_LEVEL=debug ./run_api.sh
```

- `RCA_SKIP_DOCKER_POSTGRES=1` — do not start Docker; use when `RCA_DATABASE_URL` points at a Postgres you manage (e.g. cloud or a local install not on `127.0.0.1:5433`).
- `run_api.sh` uses `--loop asyncio` by default (`LOOP_IMPL=asyncio`) for better macOS stability. You can override with `LOOP_IMPL=auto` if needed.

To run uvicorn yourself (after Postgres is up and migrated):

```bash
cd backend
export PYTHONPATH=.
export RCA_DATABASE_URL="postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca"
python3 -m alembic upgrade head
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Use `python3 -m uvicorn` so the same interpreter that has FastAPI/uvicorn is used. The bare `uvicorn` command only works if that interpreter’s `bin` directory is on your `PATH` (e.g. after `source .venv/bin/activate`).

### Web UI (Vite) + CORS

The React app in `../frontend` runs on a different origin (e.g. `http://localhost:5173`) than the API (`http://127.0.0.1:8000`). The API enables **CORS** for `localhost` / `127.0.0.1` on any port so browser `fetch()` works. Restart the API after pulling changes if buttons in the UI did nothing before.

### Environment


| Variable                           | Default                             | Meaning                                                                                                                                                                                                                                                                                                                    |
| ---------------------------------- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RCA_DATABASE_URL`                 | `postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca` | Async SQLAlchemy URL (`postgresql+asyncpg://...`).                                                                                                                                                                                                                                   |
| `RCA_INGEST_SYNC`                  | `0` (false)                         | If `1` / `true`, `POST /v1/traces` writes in the request and returns **201**. If false, traces are first persisted to the `ingest_jobs` backlog and API returns **202**; worker drains backlog to `traces`.                                                                                                                |
| `RCA_INGEST_QUEUE_MAXSIZE`         | `10000`                             | Max backlog row count (`ingest_jobs`) before API returns **503**                                                                                                                                                                                                                                                           |
| `RCA_INGEST_BATCH_MAX_SIZE`        | `100`                               | Max items accepted by `POST /v1/traces/batch`                                                                                                                                                                                                                                                                              |
| `RCA_INGEST_MAX_STEPS_PER_TRACE`   | `500`                               | Hard cap on `steps` per trace payload. Oversized traces are rejected (**422**) and batch items are marked invalid.                                                                                                                                                                                                         |
| `RCA_INGEST_MAX_PAYLOAD_BYTES`     | `1048576`                           | Hard cap on request body size for ingest endpoints (`POST /v1/traces`, `POST /v1/traces/batch`). Oversized payloads are rejected with **413** before ingest processing.                                                                                                                                                  |
| `RCA_INGEST_MAX_STEP_ERROR_BYTES`  | `8192`                              | Max UTF-8 byte size for each step `error` string; violations return **422**.                                                                                                                                                                                                                                               |
| `RCA_INGEST_MAX_STEP_METADATA_BYTES` | `32768`                           | Max serialized JSON size for each step `metadata`; violations return **422**.                                                                                                                                                                                                                                              |
| `RCA_INGEST_MAX_STEP_INPUT_BYTES`  | `65536`                             | Max serialized JSON size for each step `input`; violations return **422**.                                                                                                                                                                                                                                                 |
| `RCA_INGEST_MAX_STEP_OUTPUT_BYTES` | `131072`                            | Max serialized JSON size for each step `output`; violations return **422**.                                                                                                                                                                                                                                                |
| `RCA_INGEST_CLAIM_TIMEOUT_SECONDS` | `60`                                | Background worker claim lease timeout; stale `processing` jobs become reclaimable                                                                                                                                                                                                                                          |
| `RCA_INGEST_RETRY_DELAY_SECONDS`   | `5`                                 | Delay before retrying failed background ingest jobs                                                                                                                                                                                                                                                                        |
| `RCA_INGEST_MAX_ATTEMPTS`          | `5`                                 | Max background attempts before moving job to `dead` state                                                                                                                                                                                                                                                                  |
| `RCA_INGEST_RATE_LIMIT_RPS`        | `0` (disabled)                      | Per-tenant ingest request limit (requests/second). When exceeded, API returns **429** with `Retry-After`.                                                                                                                                                                                                                  |
| `RCA_INGEST_DAILY_TRACE_QUOTA`     | `0` (disabled)                      | Per-tenant ingest quota (trace count/day UTC). Applied to single and batch ingest. Exceeding returns **429** with `Retry-After`.                                                                                                                                                                                           |
| `RCA_API_KEYS`                     | *(empty)*                           | JSON object mapping API key → `tenant_id`, e.g. `{"sk_example":"org_123"}`. When set, clients must send `Authorization: Bearer <key>` or `X-API-Key`. `X-Tenant-ID` is not used for auth (body `tenant_id` must still match the resolved tenant). When empty, local/dev behavior uses `X-Tenant-ID` only. |
| `RCA_JWT_SECRET`                   | *(empty / disabled)*                | Enables bearer JWT auth when set. API resolves tenant from JWT claim (`RCA_JWT_TENANT_CLAIM`, default `tenant_id`).                                                                                                                                                                                                        |
| `RCA_JWT_ALGORITHM`                | `HS256`                             | JWT verification algorithm (HMAC path for now).                                                                                                                                                                                                                                                                            |
| `RCA_JWT_TENANT_CLAIM`             | `tenant_id`                         | Claim name containing tenant binding.                                                                                                                                                                                                                                                                                      |
| `RCA_JWT_ISSUER`                   | *(empty / optional)*                | Optional expected JWT `iss`.                                                                                                                                                                                                                                                                                               |
| `RCA_JWT_AUDIENCE`                 | *(empty / optional)*                | Optional expected JWT `aud`.                                                                                                                                                                                                                                                                                               |
| `RCA_ADMIN_TOKEN`                  | *(empty / disabled)*                | Enables admin APIs for per-tenant limits via `X-Admin-Token`.                                                                                                                                                                                                                                                              |
| `RCA_S3_BUCKET`                    | *(empty)*                           | When set, full trace JSON is stored in this bucket under `{urlencoded_tenant_id}/{trace_id}/trace.json` (environment is **not** in the path). The `traces` row keeps metadata, `step_count`, `blob_key`, `blob_etag`, and an empty `payload` JSON. When empty, behavior is unchanged (full JSON in Postgres).        |
| `RCA_S3_ENDPOINT_URL`            | *(empty)*                           | S3-compatible API base URL, e.g. `http://127.0.0.1:9000` for MinIO. Empty uses default AWS endpoints.                                                                                                                                                                                                                                                                 |
| `RCA_S3_REGION`                    | `us-east-1`                         | Region passed to boto3.                                                                                                                                                                                                                                                                                                    |
| `RCA_S3_ACCESS_KEY_ID`             | *(empty)*                           | Optional; if empty, boto3 uses the usual AWS environment/credential chain (`AWS_ACCESS_KEY_ID`, etc.).                                                                                                                                                                                                                      |
| `RCA_S3_SECRET_ACCESS_KEY`         | *(empty)*                           | Optional; pairs with `RCA_S3_ACCESS_KEY_ID` when set.                                                                                                                                                                                                                                                                       |

S3 runtime behavior (current):
- Blob `put/get` uses bounded retry with exponential backoff + jitter for transient S3/network failures.
- API logs include blob operation success/failure with `attempt` and `elapsed_ms` for debugging.
- Lifecycle/retention policy, DB↔blob reconciliation jobs, and admin repair tooling are deferred roadmap items.


For local async testing, use `export RCA_INGEST_SYNC=0` (or unset), post a trace, then `GET` it (may need a short delay while worker drains backlog).

- OpenAPI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
- Ingest: `POST /v1/traces` with auth as above; bearer token may be API key or JWT. JSON `tenant_id` must match the authenticated tenant (**201** if sync ingest, **202** if queued)  
- Batch ingest: `POST /v1/traces/batch` with body `{ "traces": [...] }` and the same auth headers  
  - **201** when all items are synchronously accepted, **202** when all are queued, **207** for mixed outcomes  
  - SDK-friendly item fields: `status`, `http_status`, optional `error_code`, optional `detail`
- Rate/quota failures return **429** with `Retry-After` and a retry hint in `detail`.
- List: `GET /v1/traces?limit=&offset=&status=&environment=&started_at_from=&started_at_to=` — optional filters; time bounds are **inclusive** on `started_at` (run time), ISO-8601
- Steps query: `GET /v1/traces/steps?step_type=&has_error=&days=&environment=&limit=&offset=` — fast step-index query (supports failures/success/all; default `days=7`)
- Backward-compatible alias: `GET /v1/traces/steps/failures?...` (equivalent to `has_error=true`)
- Fetch: `GET /v1/traces/{trace_id}?environment=prod|staging|dev|critical` (defaults to `prod`)  
- Diagnosis (rules v1): `GET /v1/traces/{trace_id}/diagnosis?environment=...` (defaults to `prod`) — primary hypothesis, confidence, evidence
- Admin limits (when `RCA_ADMIN_TOKEN` is set):
  - `GET /v1/admin/tenants/{tenant_id}/limits`
  - `PUT /v1/admin/tenants/{tenant_id}/limits` with `{ "ingest_rate_limit_rps": int>=0, "ingest_daily_trace_quota": int>=0 }`

## Tests

Tests use PostgreSQL database **`rca_test`** on the same host/port as local dev (`postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca_test`). Start Postgres first (e.g. run `./run_api.sh` once, or `docker compose -f docker-compose.postgres.yml up -d` and create `rca_test` if needed). `tests/conftest.py` creates `rca_test` when it can connect to the `postgres` maintenance DB.

```bash
cd backend
export PYTHONPATH=.
pytest -v
```

## Migrations (Alembic)

The app runs `alembic upgrade head` during startup (`init_db`), so schema is migrated before serving.

```bash
cd backend
export PYTHONPATH=.
python3 -m alembic upgrade head
```

## Data model notes

- **`UNIQUE (tenant_id, trace_id)`** on `traces`, `diagnoses`, and `ingest_jobs` (and **`UNIQUE (tenant_id, trace_id, step_id)`** on `trace_steps`). The same `trace_id` may exist under **different** tenants; **409** if that pair already exists for the authenticated tenant.
- Each step supports **`step_version`** (default `1.0`) so `input`/`output`/`metadata` can evolve per-step without forcing an immediate top-level trace schema bump.
- **`environment`** (`prod|staging|dev|critical`, default `prod`) is **metadata** for filtering and display (e.g. list queries and optional match on `GET` detail/diagnosis). It is **not** a second namespace for identity: traces are **issued by this system** with one logical id per tenant; clients mainly **log** that id. Re-posting the same `trace_id` with different `environment` or payload is treated as a duplicate, not a second trace—**updates** to an existing trace will be a separate API path when added.
- Current rate limiter is **in-process** (per API process). For multi-instance deployments, move rate/quota state to shared storage (e.g. Redis/Postgres).
- Per-tenant policy overrides are persisted in `tenant_limits` and applied before global defaults.
- Background ingest uses claim/ack/release semantics (Postgres uses `FOR UPDATE SKIP LOCKED`) for safe multi-worker processing.

## Next implementation steps (see `plan.md` §19)

1. **Object storage** tuning and staging/prod hardening (S3 already optional).
2. **Distributed rate-limiter backend** (Redis/Postgres counters) for multi-instance API nodes.
3. **Python SDK** and **LLM explainer** — as in `plan.md`. The web console already lives in `frontend/`.
