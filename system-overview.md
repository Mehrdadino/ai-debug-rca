# System overview

Concise map of the **ai-debug-rca** stack: API surface, persistence, async ingest, optional object storage, and the web UI. For product strategy and roadmap, see `plan.md`.

## Architecture (high level)

Mermaid renders differently in GitHub, VS Code, and other tools; `<br/>` in node labels often shows as raw text, and floating nodes produce stray arrows. This section uses **plain text** instead.

```
  React UI  ──┐
              ├──►  FastAPI  ──►  OLTP database (PostgreSQL; local via Docker)
  SDK/scripts ┘         │              ▲
                        │              │
                        │         same DB used by:
                        │              │
                   Ingest worker  ─────┘
                   (asyncio background task when RCA_INGEST_SYNC is off;
                    claims ingest_jobs, writes traces / trace_steps / diagnoses)

  Optional object storage (only if RCA_S3_BUCKET is set):

        Ingest worker  ──PUT full JSON──►  S3-compatible bucket
        FastAPI        ◄─GET if blob_key──  (same bucket; key = tenant_id/trace_id/trace.json)
```

**Flows**

| Path | What happens |
|------|----------------|
| **Synchronous** | Client → FastAPI → OLTP (read/write lists, limits, sync ingest when `RCA_INGEST_SYNC`, enqueue row in `ingest_jobs` when async). |
| **Background ingest** | Worker loop polls `ingest_jobs`, persists `traces` + `trace_steps` + `diagnoses`; if S3 enabled, uploads full JSON then stores `blob_key` on `traces`. |
| **Optional S3** | Detail `GET` loads full JSON from S3 when `blob_key` is set; otherwise from `traces.payload`. |

- **Default DB:** PostgreSQL (`RCA_DATABASE_URL`, local `docker-compose.postgres.yml` on port 5433; `./run_api.sh` starts it).
- **Object storage:** only used when `RCA_S3_BUCKET` is set; otherwise full trace JSON lives in `traces.payload`.

---

## HTTP API

Base URL is wherever the API is hosted (e.g. `http://127.0.0.1:8000`). OpenAPI: **`/docs`**.

### Health

| Method | Path | Purpose |
|--------|------|--------|
| `GET` | `/health` | Liveness; returns `{"status":"ok"}` |

### Traces (`/v1/traces`)

| Method | Path | Purpose |
|--------|------|--------|
| `POST` | `/v1/traces` | Ingest one canonical trace. **201** if `RCA_INGEST_SYNC` persists in-request; **202** if queued to `ingest_jobs`. **409** duplicate `(tenant_id, trace_id)`. **429** rate/quota. |
| `POST` | `/v1/traces/batch` | Batch ingest; per-item outcomes (**201/202/409/422/503** semantics; **207** when mixed). |
| `GET` | `/v1/traces` | Paginated list (`limit`, `offset`), optional filters: `status`, `environment`, `started_at_from`, `started_at_to`. |
| `GET` | `/v1/traces/{trace_id}` | Full trace JSON (`environment` query param must match stored row). Loads body from **S3** if `blob_key` is set, else from **`traces.payload`**. |
| `GET` | `/v1/traces/{trace_id}/diagnosis` | Rule-based `DiagnosisRecord` for that trace + environment. |
| `GET` | `/v1/traces/steps` | Step index query: `days`, `step_type`, `has_error`, `environment`, pagination. |
| `GET` | `/v1/traces/steps/failures` | Alias for steps with `has_error=true`. |

### Admin (`/v1/admin/tenants`)

Requires **`X-Admin-Token`** when `RCA_ADMIN_TOKEN` is set.

| Method | Path | Purpose |
|--------|------|--------|
| `GET` | `/v1/admin/tenants/{tenant_id}/limits` | Read per-tenant ingest RPS cap and daily trace quota. |
| `PUT` | `/v1/admin/tenants/{tenant_id}/limits` | Update those limits. |

### Auth (tenant resolution)

- **Dev:** `X-Tenant-ID` + body `tenant_id` must match (when API keys / JWT are off).
- **Production-style:** `RCA_API_KEYS` JSON → `Authorization: Bearer` or `X-API-Key`; or JWT (`RCA_JWT_*`) with tenant claim.

---

## Database tables (OLTP)

| Table | Role |
|-------|------|
| **`traces`** | One row per `(tenant_id, trace_id)`: metadata (`environment`, `status`, `started_at`, …), **`step_count`**, **`payload`** (full JSON or `{}` when offloaded), **`blob_key`** / **`blob_etag`** when using S3. |
| **`trace_steps`** | Denormalized step index for cross-trace queries (Steps tab / `GET /v1/traces/steps`). |
| **`diagnoses`** | Rule-engine output per trace (`DiagnosisRecord` JSON). |
| **`ingest_jobs`** | Durable queue for async ingest: payload JSON, claim/ack/retry fields. |
| **`tenant_limits`** | Per-tenant ingest RPS and daily trace quota (admin APIs). |

Uniqueness: **`(tenant_id, trace_id)`** on traces, diagnoses, and ingest_jobs; **`(tenant_id, trace_id, step_id)`** on `trace_steps`.

---

## PostgreSQL vs S3

| Store | What lives there |
|-------|-------------------|
| **OLTP (PostgreSQL)** | All table rows above. Always: metadata, step index, diagnosis, queue, limits. **Either** full trace JSON in `traces.payload` **or**, when blob mode is on, an **empty** `payload` with **`blob_key`** pointing at the object. |
| **S3-compatible bucket** (optional) | **Only** when `RCA_S3_BUCKET` is set: one object per trace, key **`{url-encoded tenant_id}/{trace_id}/trace.json`** (environment is **not** in the path). Full canonical trace JSON bytes. |

**Reads:** `GET /v1/traces/{id}` uses **`blob_key`** → fetch S3; else **`payload`** in DB (supports old rows that predate S3).

---

## Ingest data flow

1. **Normalize** incoming `Trace` (defaults, validation).
2. **Duplicate check** against existing `traces` (and queue rules for async path).
3. **`RCA_INGEST_SYNC=true`:** `insert_trace` in the **same request** → **201**.
4. **`RCA_INGEST_SYNC=false` (default):** row in **`ingest_jobs`** → **202**; a **background asyncio task** (`ingest_worker`) **claims** jobs, runs **`insert_trace`**, **acks** or **retries** with backoff / max attempts.

`insert_trace` writes **`traces`** (+ **`trace_steps`**, **`diagnoses`**). If blob storage is enabled, it **PUTs** JSON to S3 first, then persists **`blob_key`** and empty **`payload`**.

---

## Web UI (React)

| Tab | Purpose |
|-----|--------|
| **Settings** | Base URL, tenant / API key / JWT / admin token, health check. |
| **Ingest** | Edit and send `POST /v1/traces` and `/v1/traces/batch` bodies. |
| **Traces** | List + filters, trace detail, execution graph, timeline, diagnosis JSON, **shareable URL** query params. |
| **Steps** | `GET /v1/traces/steps` with filters; row opens trace with step focus. |
| **Admin** | Tenant limits (needs admin token). |
| **Test Data** | Generate sample traces via API. |

The UI is a **public API client** only (no special private server).

---

## Related docs

- `plan.md` — product, roadmap, S3 credential notes (**§16.1.2**).
- `backend/README.md` — env vars, run commands, Postgres.
