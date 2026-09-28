# Contributing

Thanks for helping improve ai_debug_rca.

## Development setup

1. Backend: follow [backend/README.md](backend/README.md). `./run_api.sh` starts local Postgres, runs migrations, and serves the API on port 8000.
2. Frontend: follow [frontend/README.md](frontend/README.md).
3. Example requests: [scripts/README.md](scripts/README.md).

## Tests

From `backend/`, with Postgres available (the same local container `./run_api.sh` starts):

```bash
export PYTHONPATH=.
pytest -v
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

## Pull requests

- Keep changes focused. One concern per pull request is easier to review.
- Match existing style in the files you touch.
- Add or update tests when you change API or ingest behavior.
- Update `backend/README.md` or `system-overview.md` when you change endpoints, environment variables, or the data model.
- Do not commit secrets, `.env` files, or local database dumps. See [SECURITY.md](SECURITY.md).

## Design defaults

Production is assumed to run with more than one app instance. Ingest and background work should be idempotent, and shared queues should use an atomic claim so two workers cannot process the same job. Call out anything that only works on a single node as local-development behavior.
