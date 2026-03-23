# Example scripts (HTTP)

These bash scripts call the backend with **`curl`**. The only **POST** endpoint right now is **`POST /v1/traces`**, so each file is a different example payload (minimal, multi-step RAG, error for diagnosis, etc.).

## Prerequisites

- Backend running (e.g. `python3 -m uvicorn app.main:app --reload` from `backend/`).
- **`RCA_INGEST_SYNC=1`** recommended so the trace is stored before you `GET` it (or wait briefly if using async ingest).

## Environment

| Variable   | Default              | Meaning                          |
|-----------|----------------------|----------------------------------|
| `BASE_URL` | `http://127.0.0.1:8000` | API root (no trailing slash) |
| `TENANT`  | `org_demo`           | Sent as `X-Tenant-ID` and in JSON `tenant_id` |

Example:

```bash
export BASE_URL=http://127.0.0.1:8001
export TENANT=my_org
./scripts/post_trace_minimal.sh
```

## Scripts

| Script | Purpose |
|--------|---------|
| `post_trace_minimal.sh` | Smallest valid trace (no steps). |
| `post_trace_rag_multi_step.sh` | Retrieval + LLM steps (happy path). |
| `post_trace_diagnosis_step_error.sh` | Step error → should surface `step_error` in diagnosis. |
| `post_trace_diagnosis_empty_retrieval.sh` | Empty retrieval chunks → `empty_retrieval` rule. |

After a successful POST, each script prints the **`trace_id`** and example **`curl`** lines to fetch the trace and diagnosis.

## Run

From the repo root:

```bash
chmod +x scripts/*.sh
./scripts/post_trace_minimal.sh
```
