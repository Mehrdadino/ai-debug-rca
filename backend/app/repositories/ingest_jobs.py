from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import IngestJobRecord
from app.models.trace import Trace


class IngestJobConflictError(Exception):
    """(tenant_id, environment, trace_id) already exists in ingest backlog."""


async def queued_jobs_count(session: AsyncSession) -> int:
    q = select(func.count()).select_from(IngestJobRecord)
    result = await session.execute(q)
    return int(result.scalar_one())


async def enqueue_ingest_job(session: AsyncSession, trace: Trace) -> IngestJobRecord:
    row = IngestJobRecord(
        trace_id=str(trace.trace_id),
        tenant_id=trace.tenant_id,
        environment=trace.environment.value,
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


async def get_next_ingest_job(session: AsyncSession) -> Optional[IngestJobRecord]:
    q = select(IngestJobRecord).order_by(IngestJobRecord.created_at.asc()).limit(1)
    result = await session.execute(q)
    return result.scalar_one_or_none()


async def delete_ingest_job(session: AsyncSession, job_id: int) -> None:
    row = await session.get(IngestJobRecord, job_id)
    if row is not None:
        await session.delete(row)
    await session.commit()
