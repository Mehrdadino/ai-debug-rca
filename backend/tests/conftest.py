"""Pytest: DB URL before imports; FastAPI TestClient + truncate between tests."""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("RCA_DATABASE_URL", "sqlite+aiosqlite:///./data/pytest.db")
# Deterministic tests: write in-request (201) instead of queued (202).
os.environ.setdefault("RCA_INGEST_SYNC", "1")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _truncate_traces(client: TestClient) -> None:
    """Depends on client so lifespan + tables exist before DELETE."""

    async def truncate() -> None:
        from sqlalchemy import delete

        from app.db.engine import get_session
        from app.db.models import DiagnosisRecord, IngestJobRecord, TenantLimitRecord, TraceRecord

        async with get_session() as session:
            await session.execute(delete(TenantLimitRecord))
            await session.execute(delete(IngestJobRecord))
            await session.execute(delete(DiagnosisRecord))
            await session.execute(delete(TraceRecord))
            await session.commit()

    asyncio.run(truncate())


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    from app.config import settings
    from app.services.rate_limits import tenant_ingest_limiter

    settings.ingest_rate_limit_rps = 0
    settings.ingest_daily_trace_quota = 0
    settings.admin_token = ""
    tenant_ingest_limiter.reset()
