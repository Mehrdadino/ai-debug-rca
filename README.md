# ai-debug-rca

Universal AI debugging & root-cause analysis — product plan and implementation.

- **`plan.md`** — product, architecture, stack defaults.  
- **`backend/`** — Python (FastAPI) API. See `backend/README.md` to run locally.  
- **`frontend/`** — React + TypeScript UI console for traces, steps, admin limits, and test-data generation (`npm install && npm run dev`).
- **`scripts/`** — example `curl` scripts for `POST /v1/traces` (one script per example payload). See `scripts/README.md`.

## Troubleshooting: `ERR_CONNECTION_TIMED_OUT` to `:8000`

That means nothing accepted the TCP connection (not CORS). **Start the API** and confirm it listens:

```bash
cd backend
export PYTHONPATH=.
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal: `curl -sS http://127.0.0.1:8000/health` → should return `{"status":"ok"}`.  
If you use **Cursor remote / SSH / dev container**, the browser’s `127.0.0.1` is your **local** machine, not the remote host — forward port 8000 or set the UI **Base URL** to the reachable API URL.
