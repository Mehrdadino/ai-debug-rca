from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.config import settings
from app.db.engine import get_session
from app.db.models import TraceRecord
from app.models.diagnosis import Diagnosis
from app.models.trace import Trace, TraceStatus
from app.repositories.diagnosis import get_diagnosis_for_trace
from app.repositories.traces import (
    TraceConflictError,
    get_trace_by_id,
    insert_trace,
    list_traces,
    trace_exists,
)
from app.services.ingest_worker import (
    IngestQueueFullError,
    IngestTraceConflictError,
    enqueue_trace,
)
from app.services.normalization import normalize_trace

router = APIRouter(prefix="/v1/traces", tags=["traces"])


async def db_session() -> AsyncSession:
    async with get_session() as session:
        yield session


class IngestTraceResponse(BaseModel):
    trace_id: UUID
    status: str = Field(
        description='Either "accepted" (stored in-request) or "queued" (background worker).'
    )


class TraceSummary(BaseModel):
    trace_id: UUID
    tenant_id: str
    status: TraceStatus
    started_at: str
    ended_at: Optional[str] = None
    step_count: int = Field(description="Number of steps in the execution graph")


class TraceListResponse(BaseModel):
    items: list[TraceSummary]
    limit: int
    offset: int
    has_more: bool


def _row_to_summary(row: TraceRecord) -> TraceSummary:
    steps = row.payload.get("steps") or []
    return TraceSummary(
        trace_id=UUID(row.trace_id),
        tenant_id=row.tenant_id,
        status=TraceStatus(row.status),
        started_at=row.started_at.isoformat(),
        ended_at=row.ended_at.isoformat() if row.ended_at else None,
        step_count=len(steps) if isinstance(steps, list) else 0,
    )


@router.get("", response_model=TraceListResponse)
async def list_traces_endpoint(
    tenant_id: str = Depends(require_tenant_id),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: Optional[TraceStatus] = Query(None, description="Filter by trace status"),
) -> TraceListResponse:
    rows = await list_traces(
        session,
        tenant_id,
        status=status.value if status else None,
        limit=limit,
        offset=offset,
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return TraceListResponse(
        items=[_row_to_summary(r) for r in rows],
        limit=limit,
        offset=offset,
        has_more=has_more,
    )


@router.get("/{trace_id}/diagnosis", response_model=Diagnosis)
async def get_trace_diagnosis(
    trace_id: UUID,
    tenant_id: str = Depends(require_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> Diagnosis:
    row = await get_diagnosis_for_trace(session, tenant_id, trace_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="diagnosis not found for this trace",
        )
    return Diagnosis.model_validate(row.payload)


@router.post(
    "",
    response_model=IngestTraceResponse,
    responses={
        201: {"description": "Stored synchronously (ingest_sync mode)"},
        202: {"description": "Accepted for async persistence"},
    },
)
async def ingest_trace(
    body: Trace,
    response: Response,
    tenant_id: str = Depends(require_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> IngestTraceResponse:
    if body.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="body.tenant_id must match X-Tenant-ID header",
        )
    normalized = normalize_trace(body)

    if await trace_exists(session, tenant_id, body.trace_id):
        raise HTTPException(
            status_code=409,
            detail=f"trace_id {body.trace_id} already exists",
        )

    if settings.ingest_sync:
        try:
            await insert_trace(session, normalized)
        except TraceConflictError:
            raise HTTPException(
                status_code=409,
                detail=f"trace_id {body.trace_id} already exists",
            ) from None
        response.status_code = 201
        return IngestTraceResponse(trace_id=body.trace_id, status="accepted")

    try:
        await enqueue_trace(normalized)
    except IngestTraceConflictError:
        raise HTTPException(
            status_code=409,
            detail=f"trace_id {body.trace_id} already exists",
        ) from None
    except IngestQueueFullError:
        raise HTTPException(
            status_code=503,
            detail="ingest queue is full; retry later",
        ) from None
    response.status_code = 202
    return IngestTraceResponse(trace_id=body.trace_id, status="queued")


@router.get("/{trace_id}", response_model=Trace)
async def get_trace(
    trace_id: UUID,
    tenant_id: str = Depends(require_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> Trace:
    row = await get_trace_by_id(session, tenant_id, trace_id)
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return Trace.model_validate(row.payload)
