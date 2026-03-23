from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_tenant_id
from app.config import settings
from app.db.engine import get_session
from app.db.models import TraceRecord
from app.models.diagnosis import Diagnosis
from app.models.trace import Trace, TraceEnvironment, TraceStatus
from app.repositories.diagnosis import get_diagnosis_for_trace
from app.repositories.tenant_limits import get_tenant_limits
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
from app.services.rate_limits import resolve_effective_limits, tenant_ingest_limiter

router = APIRouter(prefix="/v1/traces", tags=["traces"])


async def db_session() -> AsyncSession:
    async with get_session() as session:
        yield session


async def _enforce_ingest_limits(session: AsyncSession, tenant_id: str, traces: int) -> None:
    configured = await get_tenant_limits(session, tenant_id)
    effective = resolve_effective_limits(configured)
    result = tenant_ingest_limiter.check_and_consume(
        tenant_id=tenant_id,
        traces=traces,
        rps_limit=effective.ingest_rate_limit_rps,
        daily_quota=effective.ingest_daily_trace_quota,
    )
    if result.allowed:
        return
    retry_headers = {"Retry-After": str(result.retry_after_seconds)}
    if result.reason == "rps_limit_exceeded":
        detail = (
            "ingest rate limit exceeded for this tenant; retry later "
            f"(retry_after_seconds={result.retry_after_seconds})"
        )
    else:
        detail = (
            "daily ingest trace quota exceeded for this tenant; retry later "
            f"(retry_after_seconds={result.retry_after_seconds})"
        )
    raise HTTPException(status_code=429, detail=detail, headers=retry_headers)


class IngestTraceResponse(BaseModel):
    trace_id: UUID
    status: str = Field(
        description='Either "accepted" (stored in-request) or "queued" (background worker).'
    )


class BatchIngestRequest(BaseModel):
    traces: list[dict[str, Any]] = Field(default_factory=list)


class BatchItemStatus(str, Enum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    CONFLICT = "conflict"
    INVALID = "invalid"
    QUEUE_FULL = "queue_full"


class BatchItemErrorCode(str, Enum):
    DUPLICATE_TRACE_ID = "duplicate_trace_id"
    VALIDATION_ERROR = "validation_error"
    QUEUE_CAPACITY_REACHED = "queue_capacity_reached"
    TENANT_MISMATCH = "tenant_mismatch"


class BatchIngestItemResult(BaseModel):
    index: int
    trace_id: Optional[UUID] = None
    status: BatchItemStatus
    http_status: int = Field(description="Equivalent per-item HTTP status semantics")
    error_code: Optional[BatchItemErrorCode] = None
    detail: Optional[str] = None


class BatchIngestResponse(BaseModel):
    total: int
    accepted: int
    queued: int
    conflicts: int
    invalid: int
    queue_full: int
    items: list[BatchIngestItemResult]


class TraceSummary(BaseModel):
    trace_id: UUID
    tenant_id: str
    environment: TraceEnvironment
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
        environment=TraceEnvironment(row.environment),
        status=TraceStatus(row.status),
        started_at=row.started_at.isoformat(),
        ended_at=row.ended_at.isoformat() if row.ended_at else None,
        step_count=len(steps) if isinstance(steps, list) else 0,
    )


async def _ingest_one_trace(
    trace: Trace,
    tenant_id: str,
    session: AsyncSession,
) -> IngestTraceResponse:
    if trace.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="body.tenant_id must match authenticated tenant",
        )
    normalized = normalize_trace(trace)
    if await trace_exists(session, tenant_id, trace.trace_id, trace.environment.value):
        raise HTTPException(
            status_code=409,
            detail=(
                f"trace_id {trace.trace_id} already exists for this tenant and environment "
                f"({trace.environment.value})"
            ),
        )

    if settings.ingest_sync:
        try:
            await insert_trace(session, normalized)
        except TraceConflictError:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"trace_id {trace.trace_id} already exists for this tenant and environment "
                    f"({trace.environment.value})"
                ),
            ) from None
        return IngestTraceResponse(trace_id=trace.trace_id, status="accepted")

    try:
        await enqueue_trace(normalized)
    except IngestTraceConflictError:
        raise HTTPException(
            status_code=409,
            detail=(
                f"trace_id {trace.trace_id} already exists for this tenant and environment "
                f"({trace.environment.value})"
            ),
        ) from None
    except IngestQueueFullError:
        raise HTTPException(status_code=503, detail="ingest queue is full; retry later") from None
    return IngestTraceResponse(trace_id=trace.trace_id, status="queued")


@router.get("", response_model=TraceListResponse)
async def list_traces_endpoint(
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(db_session),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    environment: Optional[TraceEnvironment] = Query(
        None,
        description="Filter by trace environment (prod/staging/dev/critical).",
    ),
    status: Optional[TraceStatus] = Query(None, description="Filter by trace status"),
    started_at_from: Optional[datetime] = Query(
        None,
        description="Inclusive lower bound on trace started_at (run time), ISO-8601.",
    ),
    started_at_to: Optional[datetime] = Query(
        None,
        description="Inclusive upper bound on trace started_at (run time), ISO-8601.",
    ),
) -> TraceListResponse:
    if started_at_from is not None and started_at_to is not None:
        if started_at_from > started_at_to:
            raise HTTPException(
                status_code=400,
                detail="started_at_from must be <= started_at_to",
            )
    rows = await list_traces(
        session,
        tenant_id,
        environment=environment.value if environment else None,
        status=status.value if status else None,
        started_at_from=started_at_from,
        started_at_to=started_at_to,
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
    environment: TraceEnvironment = Query(
        TraceEnvironment.PROD,
        description="Trace environment for this trace_id lookup. Defaults to prod.",
    ),
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> Diagnosis:
    row = await get_diagnosis_for_trace(session, tenant_id, trace_id, environment.value)
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
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> IngestTraceResponse:
    await _enforce_ingest_limits(session, tenant_id, traces=1)
    result = await _ingest_one_trace(body, tenant_id, session)
    response.status_code = 201 if result.status == "accepted" else 202
    return result


@router.post("/batch", response_model=BatchIngestResponse)
async def ingest_traces_batch(
    body: BatchIngestRequest,
    response: Response,
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> BatchIngestResponse:
    total = len(body.traces)
    if total == 0:
        raise HTTPException(status_code=400, detail="traces must contain at least one item")
    if total > settings.ingest_batch_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"batch too large: max {settings.ingest_batch_max_size}",
        )
    await _enforce_ingest_limits(session, tenant_id, traces=total)

    items: list[BatchIngestItemResult] = []
    accepted = queued = conflicts = invalid = queue_full = 0

    for idx, raw in enumerate(body.traces):
        try:
            t = Trace.model_validate(raw)
        except ValidationError as e:
            invalid += 1
            items.append(
                BatchIngestItemResult(
                    index=idx,
                    status=BatchItemStatus.INVALID,
                    http_status=422,
                    error_code=BatchItemErrorCode.VALIDATION_ERROR,
                    detail=str(e.errors()[0].get("msg", "invalid trace payload")),
                )
            )
            continue

        try:
            result = await _ingest_one_trace(t, tenant_id, session)
            if result.status == "accepted":
                accepted += 1
            else:
                queued += 1
            items.append(
                BatchIngestItemResult(
                    index=idx,
                    trace_id=result.trace_id,
                    status=(
                        BatchItemStatus.ACCEPTED
                        if result.status == "accepted"
                        else BatchItemStatus.QUEUED
                    ),
                    http_status=201 if result.status == "accepted" else 202,
                )
            )
        except HTTPException as e:
            trace_id = t.trace_id
            if e.status_code == 409:
                conflicts += 1
                status = BatchItemStatus.CONFLICT
                error_code = BatchItemErrorCode.DUPLICATE_TRACE_ID
            elif e.status_code == 503:
                queue_full += 1
                status = BatchItemStatus.QUEUE_FULL
                error_code = BatchItemErrorCode.QUEUE_CAPACITY_REACHED
            elif e.status_code == 400:
                invalid += 1
                status = BatchItemStatus.INVALID
                error_code = BatchItemErrorCode.TENANT_MISMATCH
            else:
                invalid += 1
                status = BatchItemStatus.INVALID
                error_code = BatchItemErrorCode.VALIDATION_ERROR
            items.append(
                BatchIngestItemResult(
                    index=idx,
                    trace_id=trace_id,
                    status=status,
                    http_status=e.status_code,
                    error_code=error_code,
                    detail=str(e.detail),
                )
            )

    if invalid == 0 and conflicts == 0 and queue_full == 0:
        response.status_code = 201 if accepted > 0 else 202
    else:
        response.status_code = 207

    return BatchIngestResponse(
        total=total,
        accepted=accepted,
        queued=queued,
        conflicts=conflicts,
        invalid=invalid,
        queue_full=queue_full,
        items=items,
    )


@router.get("/{trace_id}", response_model=Trace)
async def get_trace(
    trace_id: UUID,
    environment: TraceEnvironment = Query(
        TraceEnvironment.PROD,
        description="Trace environment for this trace_id lookup. Defaults to prod.",
    ),
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> Trace:
    row = await get_trace_by_id(session, tenant_id, trace_id, environment.value)
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return Trace.model_validate(row.payload)
