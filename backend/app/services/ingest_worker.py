"""DB-backed ingest worker (durable backlog in ingest_jobs table)."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.config import settings
from app.db.engine import get_session
from app.models.trace import Trace
from app.repositories.ingest_jobs import (
    IngestJobConflictError,
    delete_ingest_job,
    enqueue_ingest_job,
    get_next_ingest_job,
    queued_jobs_count,
)
from app.repositories.traces import TraceConflictError, insert_trace

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task[None]] = None


async def enqueue_trace(trace: Trace) -> None:
    async with get_session() as session:
        count = await queued_jobs_count(session)
        if count >= settings.ingest_queue_maxsize:
            raise IngestQueueFullError from None
        try:
            await enqueue_ingest_job(session, trace)
        except IngestJobConflictError:
            raise IngestTraceConflictError from None


class IngestQueueFullError(Exception):
    """Ingest queue is at capacity."""


class IngestTraceConflictError(Exception):
    """trace_id already present in backlog."""


async def _worker_loop() -> None:
    while True:
        async with get_session() as session:
            job = await get_next_ingest_job(session)
        if job is None:
            await asyncio.sleep(0.2)
            continue

        trace = Trace.model_validate(job.payload)
        try:
            async with get_session() as session:
                await insert_trace(session, trace)
        except TraceConflictError:
            logger.warning(
                "ingest worker: duplicate trace_id (race), skipping: %s", trace.trace_id
            )
        except Exception:
            logger.exception("ingest worker: failed to persist trace_id=%s", trace.trace_id)
        finally:
            # Remove from backlog after successful insert, or after duplicate conflict.
            try:
                async with get_session() as session:
                    await delete_ingest_job(session, job.id)
            except Exception:
                logger.exception(
                    "ingest worker: failed to delete job id=%s for trace_id=%s",
                    job.id,
                    trace.trace_id,
                )


def start_ingest_worker() -> None:
    global _worker_task
    if settings.ingest_sync:
        return
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop(), name="ingest-worker")


async def stop_ingest_worker() -> None:
    global _worker_task
    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
