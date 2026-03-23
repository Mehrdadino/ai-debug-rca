"""In-process asyncio queue + worker (dev); swap for SQS/Redis later."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from app.config import settings
from app.db.engine import get_session
from app.models.trace import Trace
from app.repositories.traces import TraceConflictError, insert_trace

logger = logging.getLogger(__name__)

_queue: Optional[asyncio.Queue[Trace]] = None
_worker_task: Optional[asyncio.Task[None]] = None


def _ensure_queue() -> asyncio.Queue[Trace]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue(maxsize=settings.ingest_queue_maxsize)
    return _queue


async def enqueue_trace(trace: Trace) -> None:
    q = _ensure_queue()
    try:
        q.put_nowait(trace)
    except asyncio.QueueFull:
        raise IngestQueueFullError from None


class IngestQueueFullError(Exception):
    """Ingest queue is at capacity."""


async def _worker_loop() -> None:
    q = _ensure_queue()
    while True:
        trace = await q.get()
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
            q.task_done()


def start_ingest_worker() -> None:
    global _worker_task
    if settings.ingest_sync:
        return
    _ensure_queue()
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop(), name="ingest-worker")


async def stop_ingest_worker() -> None:
    global _worker_task, _queue
    if _worker_task is not None and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        _worker_task = None
    _queue = None
