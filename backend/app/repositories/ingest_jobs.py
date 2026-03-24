from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestJobRecord
from app.models.trace import Trace


class IngestJobConflictError(Exception):
    """(tenant_id, trace_id) already exists in ingest backlog."""


async def queued_jobs_count(session: AsyncSession) -> int:
    q = (
        select(func.count())
        .select_from(IngestJobRecord)
        .where(IngestJobRecord.status.in_(("queued", "processing")))
    )
    result = await session.execute(q)
    return int(result.scalar_one())


async def enqueue_ingest_job(session: AsyncSession, trace: Trace) -> IngestJobRecord:
    now = datetime.now(timezone.utc)
    row = IngestJobRecord(
        trace_id=str(trace.trace_id),
        tenant_id=trace.tenant_id,
        environment=trace.environment.value,
        status="queued",
        attempts=0,
        claimed_at=None,
        claimed_by=None,
        available_at=now,
        last_error=None,
        payload=trace.model_dump(mode="json"),
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise IngestJobConflictError from e
    await session.refresh(row)
    return row


async def claim_next_ingest_job(
    session: AsyncSession,
    *,
    worker_id: str,
    claim_timeout_seconds: int,
) -> Optional[IngestJobRecord]:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=claim_timeout_seconds)
    dialect = session.bind.dialect.name if session.bind is not None else ""

    if dialect == "postgresql":
        claim_sql = text(
            """
            WITH candidate AS (
                SELECT id
                FROM ingest_jobs
                WHERE
                    (
                        status = 'queued'
                        OR (status = 'processing' AND claimed_at < :stale_before)
                    )
                    AND available_at <= :now
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE ingest_jobs j
            SET
                status = 'processing',
                claimed_at = :now,
                claimed_by = :worker_id,
                attempts = j.attempts + 1,
                last_error = NULL
            FROM candidate
            WHERE j.id = candidate.id
            RETURNING j.id
            """
        )
        result = await session.execute(
            claim_sql,
            {"now": now, "stale_before": stale_before, "worker_id": worker_id},
        )
        claimed_id = result.scalar_one_or_none()
        if claimed_id is None:
            await session.rollback()
            return None
        await session.commit()
        return await session.get(IngestJobRecord, claimed_id)

    # SQLite/dev fallback: optimistic claim with status guard.
    q = (
        select(IngestJobRecord.id)
        .where(
            IngestJobRecord.status == "queued",
            IngestJobRecord.available_at <= now,
        )
        .order_by(IngestJobRecord.created_at.asc())
        .limit(1)
    )
    result = await session.execute(q)
    candidate_id = result.scalar_one_or_none()
    if candidate_id is None:
        await session.rollback()
        return None
    upd = (
        update(IngestJobRecord)
        .where(
            IngestJobRecord.id == candidate_id,
            IngestJobRecord.status == "queued",
        )
        .values(
            status="processing",
            claimed_at=now,
            claimed_by=worker_id,
            attempts=IngestJobRecord.attempts + 1,
            last_error=None,
        )
    )
    claimed = await session.execute(upd)
    if claimed.rowcount == 0:
        await session.rollback()
        return None
    await session.commit()
    return await session.get(IngestJobRecord, candidate_id)


async def ack_ingest_job(session: AsyncSession, job_id: int) -> None:
    row = await session.get(IngestJobRecord, job_id)
    if row is not None:
        await session.delete(row)
    await session.commit()


async def release_ingest_job_for_retry(
    session: AsyncSession,
    *,
    job_id: int,
    error_message: str,
    retry_delay_seconds: int,
    max_attempts: int,
) -> None:
    row = await session.get(IngestJobRecord, job_id)
    if row is None:
        await session.commit()
        return
    now = datetime.now(timezone.utc)
    attempts = int(row.attempts)
    exhausted = attempts >= max_attempts
    row.status = "dead" if exhausted else "queued"
    row.last_error = error_message[:2000]
    row.claimed_at = None
    row.claimed_by = None
    row.available_at = now if exhausted else now + timedelta(seconds=retry_delay_seconds)
    await session.commit()
