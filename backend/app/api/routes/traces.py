from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_tenant_id
from app.db.engine import get_session
from app.models.trace import Trace
from app.repositories.traces import TraceConflictError, get_trace_by_id, insert_trace
from app.services.normalization import normalize_trace

router = APIRouter(prefix="/v1/traces", tags=["traces"])


async def db_session() -> AsyncSession:
    async with get_session() as session:
        yield session


class IngestTraceResponse(BaseModel):
    trace_id: UUID
    status: str = Field(description="accepted")


@router.post("", response_model=IngestTraceResponse, status_code=201)
async def ingest_trace(
    body: Trace,
    tenant_id: str = Depends(require_tenant_id),
    session: AsyncSession = Depends(db_session),
) -> IngestTraceResponse:
    if body.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="body.tenant_id must match X-Tenant-ID header",
        )
    normalized = normalize_trace(body)
    try:
        await insert_trace(session, normalized)
    except TraceConflictError:
        raise HTTPException(
            status_code=409,
            detail=f"trace_id {body.trace_id} already exists",
        ) from None
    return IngestTraceResponse(trace_id=body.trace_id, status="accepted")


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
