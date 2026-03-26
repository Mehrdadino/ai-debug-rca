import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin_limits, health, traces
from app.config import settings
from app.db.engine import close_db, init_db
from app.services.ingest_worker import start_ingest_worker, stop_ingest_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("lifespan startup begin")
    try:
        await init_db()
        logger.info("lifespan init_db complete")
        if not settings.ingest_sync:
            start_ingest_worker()
            logger.info("lifespan ingest worker started")
        yield
    except BaseException as exc:
        print(f"[startup-error] {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        logger.exception("lifespan failed")
        raise
    finally:
        logger.info("lifespan shutdown begin")
        await stop_ingest_worker()
        await close_db()
        logger.info("lifespan shutdown complete")


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


@app.middleware("http")
async def ingest_payload_size_guard(request: Request, call_next):
    # Defensive cap against oversized ingest payloads (accidental or adversarial).
    if request.method == "POST" and request.url.path in ("/v1/traces", "/v1/traces/batch"):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > settings.ingest_max_payload_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"request body too large: content-length exceeds "
                                f"{settings.ingest_max_payload_bytes} bytes"
                            )
                        },
                    )
            except ValueError:
                # Ignore malformed header and fall back to measured body length.
                pass
        body = await request.body()
        if len(body) > settings.ingest_max_payload_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "detail": (
                        f"request body too large: max {settings.ingest_max_payload_bytes} bytes"
                    )
                },
            )
    return await call_next(request)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "ai-debug-rca", "docs": "/docs"}
