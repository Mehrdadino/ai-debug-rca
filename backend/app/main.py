from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, traces
from app.db.engine import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="ai-debug-rca",
    description="AI debugging & root-cause analysis — ingest API (Phase 1)",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(traces.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ai-debug-rca", "docs": "/docs"}
