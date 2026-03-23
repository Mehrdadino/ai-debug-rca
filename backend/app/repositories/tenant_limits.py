from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TenantLimitRecord


@dataclass(frozen=True)
class TenantLimits:
    ingest_rate_limit_rps: int
    ingest_daily_trace_quota: int


def _coerce_non_negative(v: int) -> int:
    return v if v >= 0 else 0


async def get_tenant_limits(session: AsyncSession, tenant_id: str) -> Optional[TenantLimits]:
    q = select(TenantLimitRecord).where(TenantLimitRecord.tenant_id == tenant_id)
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return TenantLimits(
        ingest_rate_limit_rps=_coerce_non_negative(int(row.ingest_rate_limit_rps)),
        ingest_daily_trace_quota=_coerce_non_negative(int(row.ingest_daily_trace_quota)),
    )


async def upsert_tenant_limits(
    session: AsyncSession,
    tenant_id: str,
    *,
    ingest_rate_limit_rps: int,
    ingest_daily_trace_quota: int,
) -> TenantLimits:
    q = select(TenantLimitRecord).where(TenantLimitRecord.tenant_id == tenant_id)
    result = await session.execute(q)
    row = result.scalar_one_or_none()
    rps = _coerce_non_negative(int(ingest_rate_limit_rps))
    quota = _coerce_non_negative(int(ingest_daily_trace_quota))
    if row is None:
        row = TenantLimitRecord(
            tenant_id=tenant_id,
            ingest_rate_limit_rps=rps,
            ingest_daily_trace_quota=quota,
        )
        session.add(row)
    else:
        row.ingest_rate_limit_rps = rps
        row.ingest_daily_trace_quota = quota
    await session.commit()
    return TenantLimits(ingest_rate_limit_rps=rps, ingest_daily_trace_quota=quota)
