from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, traces
from app.config import settings
from app.db.engine import close_db, init_db
from app.services.ingest_worker import start_ingest_worker, stop_ingest_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    if not settings.ingest_sync:
        start_ingest_worker()
    yield
    await stop_ingest_worker()
    await close_db()


app = FastAPI(
    title="ai-debug-rca",
    description="AI debugging & root-cause analysis — ingest + list API (Phase 2)",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(traces.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ai-debug-rca", "docs": "/docs"}
