# Web console

React + TypeScript UI for the ai_debug_rca API. It is a browser client: it calls the public HTTP API and does not embed server credentials.

## Run

The API should already be up (`../backend/run_api.sh`, default `http://127.0.0.1:8000`).

```bash
cd frontend
npm install
npm run dev
```

Vite prints a local URL (usually `http://localhost:5173`). In **Settings**, set Base URL to the API. Leave API key and JWT empty for local dev and set a tenant id; the client sends that as `X-Tenant-ID`.

```bash
npm run lint
npm run build
```

## Tabs

| Tab | What it does |
|-----|----------------|
| Settings | Base URL, tenant, optional API key / JWT / admin token, health check |
| Ingest | Edit and send `POST /v1/traces` and `POST /v1/traces/batch` |
| Traces | List, filters, detail, execution graph, timeline, diagnosis, shareable query params |
| Steps | Step index (`GET /v1/traces/steps`); a row opens that trace |
| Admin | Per-tenant limits; needs `RCA_ADMIN_TOKEN` on the API and the admin token in Settings |
| Test Data | Generate sample traces through the API |

The API allows browser requests from `localhost` and `127.0.0.1` on any port. Restart the API if the UI cannot reach it after a CORS-related change.
