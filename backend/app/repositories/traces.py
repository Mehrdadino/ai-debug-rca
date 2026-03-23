from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TraceRecord
from app.models.trace import Trace


class TraceConflictError(Exception):
    """trace_id already exists."""


async def insert_trace(session: AsyncSession, trace: Trace) -> TraceRecord:
    payload = trace.model_dump(mode="json")
    row = TraceRecord(
        trace_id=str(trace.trace_id),
        tenant_id=trace.tenant_id,
        status=trace.status.value,
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        payload=payload,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise TraceConflictError from e
    await session.refresh(row)
    return row


async def get_trace_by_id(
    session: AsyncSession, tenant_id: str, trace_id: UUID
) -> Optional[TraceRecord]:
    q = select(TraceRecord).where(
        TraceRecord.trace_id == str(trace_id),
        TraceRecord.tenant_id == tenant_id,
    )
    result = await session.execute(q)
    return result.scalar_one_or_none()
