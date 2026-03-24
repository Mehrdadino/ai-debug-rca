from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin_limits, health, traces
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
    description="AI debugging & root-cause analysis — durable async ingest, list, diagnosis",
    version="0.4.0",
    lifespan=lifespan,
)

# Browser UI (Vite dev server, etc.) runs on a different origin than the API; without CORS,
# fetch() is blocked and buttons appear to do nothing.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(traces.router)
app.include_router(admin_limits.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ai-debug-rca", "docs": "/docs"}
