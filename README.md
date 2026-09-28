# ai_debug_rca

Open-source API and web console for debugging AI application traces and producing a rule-based root-cause diagnosis.

You send a canonical trace (steps such as retrieval, tool calls, and LLM calls). The API stores it in PostgreSQL, optionally offloads the full JSON to S3-compatible storage, and returns a diagnosis with a primary hypothesis, confidence, and evidence. A React console lists traces, shows the execution graph and timeline, and can send sample payloads.

This repository is early-stage (API version **0.4.0**). Product direction and the longer roadmap live in [`plan.md`](plan.md). A shorter map of the running system is in [`system-overview.md`](system-overview.md).

## What you need

- Python **3.9+** (3.11+ recommended)
- Docker, for the local Postgres container on port **5433**
- Node.js and npm, for the web UI

## Quick start

**API** (starts Postgres, migrates, then serves `http://127.0.0.1:8000`):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
./run_api.sh
```

Check it: `curl -sS http://127.0.0.1:8000/health` returns `{"status":"ok"}`. Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

**Web UI** (Vite, usually `http://localhost:5173`):

```bash
cd frontend
npm install
npm run dev
```

In the UI **Settings** tab, set Base URL to `http://127.0.0.1:8000`. With API keys and JWT unset, also set a tenant id (the API reads `X-Tenant-ID`).

**Example traces** from the repo root, while the API is running:

```bash
chmod +x scripts/*.sh
./scripts/post_trace_minimal.sh
```

Full environment variables, endpoints, and tests: [`backend/README.md`](backend/README.md). Script list: [`scripts/README.md`](scripts/README.md).

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI service, Alembic migrations, pytest suite |
| `frontend/` | React + TypeScript console |
| `scripts/` | `curl` examples for single and batch ingest |
| `plan.md` | Product and architecture plan |
| `system-overview.md` | Current API, tables, and UI |

## Local credentials

`backend/docker-compose.postgres.yml` uses database user `rca` and password `rca` on `127.0.0.1:5433`. That account exists only for local development. Do not reuse it for a shared or production database.

API keys, the JWT secret, the admin token, and S3 credentials are read from the environment. To override defaults, copy [`.env.example`](.env.example) to `backend/.env` (the API loads `.env` from its working directory). `.env` is gitignored.

If `RCA_API_KEYS` and `RCA_JWT_SECRET` are empty, any client can pick a tenant with `X-Tenant-ID`. Turn on API keys or JWT before the API is reachable beyond your machine.

## Troubleshooting

`ERR_CONNECTION_TIMED_OUT` to port 8000 means nothing accepted the TCP connection. Start the API with `./run_api.sh` from `backend/`.

If you use a remote dev environment, the browser’s `127.0.0.1` is your local machine, not the remote host. Forward port 8000, or set the UI Base URL to an address the browser can reach.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Security reports: [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE).
