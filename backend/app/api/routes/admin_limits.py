from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_token
from app.db.engine import get_session
from app.repositories.tenant_limits import get_tenant_limits, upsert_tenant_limits

router = APIRouter(
    prefix="/v1/admin/tenants",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


async def db_session() -> AsyncSession:
    async with get_session() as session:
        yield session


class TenantLimitsPayload(BaseModel):
    ingest_rate_limit_rps: int = Field(0, ge=0)
    ingest_daily_trace_quota: int = Field(0, ge=0)


class TenantLimitsResponse(BaseModel):
    tenant_id: str
    ingest_rate_limit_rps: int
    ingest_daily_trace_quota: int


@router.get("/{tenant_id}/limits", response_model=TenantLimitsResponse)
async def get_limits(tenant_id: str, session: AsyncSession = Depends(db_session)) -> TenantLimitsResponse:
    current = await get_tenant_limits(session, tenant_id)
    if current is None:
        return TenantLimitsResponse(
            tenant_id=tenant_id,
            ingest_rate_limit_rps=0,
            ingest_daily_trace_quota=0,
        )
    return TenantLimitsResponse(
        tenant_id=tenant_id,
        ingest_rate_limit_rps=current.ingest_rate_limit_rps,
        ingest_daily_trace_quota=current.ingest_daily_trace_quota,
    )


@router.put("/{tenant_id}/limits", response_model=TenantLimitsResponse)
async def set_limits(
    tenant_id: str,
    body: TenantLimitsPayload,
    session: AsyncSession = Depends(db_session),
) -> TenantLimitsResponse:
    updated = await upsert_tenant_limits(
        session,
        tenant_id,
        ingest_rate_limit_rps=body.ingest_rate_limit_rps,
        ingest_daily_trace_quota=body.ingest_daily_trace_quota,
    )
    return TenantLimitsResponse(
        tenant_id=tenant_id,
        ingest_rate_limit_rps=updated.ingest_rate_limit_rps,
        ingest_daily_trace_quota=updated.ingest_daily_trace_quota,
    )
