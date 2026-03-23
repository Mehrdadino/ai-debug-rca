from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db.engine import get_session
from app.models.trace import Trace
from app.repositories.ingest_jobs import (
    ack_ingest_job,
    claim_next_ingest_job,
    enqueue_ingest_job,
    queued_jobs_count,
    release_ingest_job_for_retry,
)


def _trace() -> Trace:
    return Trace.model_validate(
        {
            "schema_version": "1.0",
            "trace_id": str(uuid4()),
            "tenant_id": "org_jobs",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "steps": [],
            "edges": [],
        }
    )


@pytest.mark.asyncio
async def test_claim_prevents_double_pick_until_ack_or_release() -> None:
    async with get_session() as session:
        await enqueue_ingest_job(session, _trace())

    async with get_session() as session:
        job1 = await claim_next_ingest_job(
            session,
            worker_id="w1",
            claim_timeout_seconds=60,
        )
    assert job1 is not None
    assert job1.status == "processing"
    assert int(job1.attempts) == 1

    async with get_session() as session:
        job2 = await claim_next_ingest_job(
            session,
            worker_id="w2",
            claim_timeout_seconds=60,
        )
    assert job2 is None

    async with get_session() as session:
        await release_ingest_job_for_retry(
            session,
            job_id=job1.id,
            error_message="temporary error",
            retry_delay_seconds=0,
            max_attempts=5,
        )

    async with get_session() as session:
        job3 = await claim_next_ingest_job(
            session,
            worker_id="w3",
            claim_timeout_seconds=60,
        )
    assert job3 is not None
    assert int(job3.attempts) == 2

    async with get_session() as session:
        await ack_ingest_job(session, job3.id)


@pytest.mark.asyncio
async def test_release_marks_dead_after_max_attempts() -> None:
    async with get_session() as session:
        await enqueue_ingest_job(session, _trace())

    async with get_session() as session:
        job = await claim_next_ingest_job(
            session,
            worker_id="w1",
            claim_timeout_seconds=60,
        )
    assert job is not None

    async with get_session() as session:
        await release_ingest_job_for_retry(
            session,
            job_id=job.id,
            error_message="permanent error",
            retry_delay_seconds=0,
            max_attempts=1,
        )

    async with get_session() as session:
        count = await queued_jobs_count(session)
    assert count == 0
