from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosisRecord, TraceRecord, TraceStepRecord
from app.models.trace import Trace
from app.services.rules_engine import evaluate_trace


class TraceConflictError(Exception):
    """(tenant_id, trace_id) already exists for this tenant."""


async def insert_trace(session: AsyncSession, trace: Trace) -> TraceRecord:
    payload = trace.model_dump(mode="json")
    row = TraceRecord(
        trace_id=str(trace.trace_id),
        tenant_id=trace.tenant_id,
        environment=trace.environment.value,
        status=trace.status.value,
        started_at=trace.started_at,
        ended_at=trace.ended_at,
        payload=payload,
    )
    session.add(row)
    diagnosis = evaluate_trace(trace)
    session.add(
        DiagnosisRecord(
            trace_id=str(trace.trace_id),
            tenant_id=trace.tenant_id,
            environment=trace.environment.value,
            payload=diagnosis.model_dump(mode="json"),
        )
    )
    for step in trace.steps:
        session.add(
            TraceStepRecord(
                trace_id=str(trace.trace_id),
                tenant_id=trace.tenant_id,
                environment=trace.environment.value,
                step_id=step.step_id,
                step_type=step.type,
                parent_step_id=step.parent_step_id,
                has_error=step.error is not None,
                error=step.error,
                trace_started_at=trace.started_at,
                input_payload=step.input,
                output_payload=step.output,
                metadata_payload=step.metadata,
                span_id=step.span_id,
                traceparent=step.traceparent,
            )
        )
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise TraceConflictError from e
    await session.refresh(row)
    return row


async def get_trace_by_id(
    session: AsyncSession,
    tenant_id: str,
    trace_id: UUID,
) -> Optional[TraceRecord]:
    q = select(TraceRecord).where(
        TraceRecord.trace_id == str(trace_id),
        TraceRecord.tenant_id == tenant_id,
    )
    result = await session.execute(q)
    return result.scalar_one_or_none()


async def trace_exists(
    session: AsyncSession,
    tenant_id: str,
    trace_id: UUID,
) -> bool:
    q = (
        select(func.count())
        .select_from(TraceRecord)
        .where(
            TraceRecord.trace_id == str(trace_id),
            TraceRecord.tenant_id == tenant_id,
        )
    )
    result = await session.execute(q)
    n = result.scalar_one()
    return int(n) > 0


async def list_traces(
    session: AsyncSession,
    tenant_id: str,
    *,
    environment: Optional[str] = None,
    status: Optional[str] = None,
    started_at_from: Optional[datetime] = None,
    started_at_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TraceRecord]:
    q = select(TraceRecord).where(TraceRecord.tenant_id == tenant_id)
    if environment is not None:
        q = q.where(TraceRecord.environment == environment)
    if status is not None:
        q = q.where(TraceRecord.status == status)
    if started_at_from is not None:
        q = q.where(TraceRecord.started_at >= started_at_from)
    if started_at_to is not None:
        q = q.where(TraceRecord.started_at <= started_at_to)
    q = q.order_by(TraceRecord.started_at.desc()).offset(offset).limit(limit + 1)
    result = await session.execute(q)
    return list(result.scalars().all())


async def list_steps(
    session: AsyncSession,
    tenant_id: str,
    *,
    has_error: Optional[bool] = None,
    step_type: Optional[str] = None,
    environment: Optional[str] = None,
    started_at_from: Optional[datetime] = None,
    started_at_to: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[TraceStepRecord]:
    q = select(TraceStepRecord).where(TraceStepRecord.tenant_id == tenant_id)
    if has_error is not None:
        q = q.where(TraceStepRecord.has_error.is_(has_error))
    if step_type is not None:
        q = q.where(TraceStepRecord.step_type == step_type)
    if environment is not None:
        q = q.where(TraceStepRecord.environment == environment)
    if started_at_from is not None:
        q = q.where(TraceStepRecord.trace_started_at >= started_at_from)
    if started_at_to is not None:
        q = q.where(TraceStepRecord.trace_started_at <= started_at_to)
    q = q.order_by(TraceStepRecord.trace_started_at.desc()).offset(offset).limit(limit + 1)
    result = await session.execute(q)
    return list(result.scalars().all())
