from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DiagnosisRecord


async def get_diagnosis_for_trace(
    session: AsyncSession,
    tenant_id: str,
    trace_id: UUID,
) -> Optional[DiagnosisRecord]:
    q = select(DiagnosisRecord).where(
        DiagnosisRecord.trace_id == str(trace_id),
        DiagnosisRecord.tenant_id == tenant_id,
    )
    result = await session.execute(q)
    return result.scalar_one_or_none()
