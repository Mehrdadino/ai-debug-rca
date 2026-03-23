"""DB-backed ingest worker (durable backlog in ingest_jobs table)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

from app.config import settings
from app.db.engine import get_session
from app.models.trace import Trace
from app.repositories.ingest_jobs import (
    IngestJobConflictError,
    ack_ingest_job,
    claim_next_ingest_job,
    enqueue_ingest_job,
    queued_jobs_count,
    release_ingest_job_for_retry,
)
from app.repositories.traces import TraceConflictError, insert_trace

logger = logging.getLogger(__name__)

_worker_task: Optional[asyncio.Task[None]] = None
_worker_id = f"worker-{uuid.uuid4()}"


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
    """(tenant_id, environment, trace_id) already present in backlog."""


async def _worker_loop() -> None:
    while True:
        async with get_session() as session:
            job = await claim_next_ingest_job(
                session,
                worker_id=_worker_id,
                claim_timeout_seconds=settings.ingest_claim_timeout_seconds,
            )
        if job is None:
            await asyncio.sleep(0.2)
            continue

        trace = Trace.model_validate(job.payload)
        try:
            async with get_session() as session:
                await insert_trace(session, trace)
            async with get_session() as session:
                await ack_ingest_job(session, job.id)
        except TraceConflictError:
            logger.warning(
                "ingest worker: duplicate (tenant_id, environment, trace_id) (race), skipping: tenant=%s env=%s trace_id=%s",
                trace.tenant_id,
                trace.environment.value,
                trace.trace_id,
            )
            async with get_session() as session:
                await ack_ingest_job(session, job.id)
        except Exception:
            logger.exception("ingest worker: failed to persist trace_id=%s", trace.trace_id)
            try:
                async with get_session() as session:
                    await release_ingest_job_for_retry(
                        session,
                        job_id=job.id,
                        error_message=f"failed to persist trace_id={trace.trace_id}",
                        retry_delay_seconds=settings.ingest_retry_delay_seconds,
                        max_attempts=settings.ingest_max_attempts,
                    )
            except Exception:
                logger.exception(
                    "ingest worker: failed to release job id=%s for trace_id=%s",
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
