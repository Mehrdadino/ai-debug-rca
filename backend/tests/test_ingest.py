from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ingest_and_get_trace(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "ended_at": "2025-01-15T10:00:02Z",
        "status": "success",
        "correlation_ids": {"upstream_provider": "langfuse", "upstream_trace_id": "abc"},
        "steps": [
            {
                "step_id": "s1",
                "type": "retrieval",
                "parent_step_id": None,
                "input": {"query": "hello"},
                "output": {"chunks": []},
                "error": None,
                "metadata": {"latency_ms": 50},
            },
            {
                "step_id": "s2",
                "type": "llm_call",
                "parent_step_id": "s1",
                "input": {"messages": []},
                "output": {"text": "hi"},
                "error": None,
                "metadata": {"latency_ms": 800, "tokens": {"input": 10, "output": 5}, "model": "gpt-4"},
            },
        ],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_demo"}
    r = client.post("/v1/traces", json=body, headers=h)
    assert r.status_code == 201
    assert r.json()["trace_id"] == str(tid)

    g = client.get(f"/v1/traces/{tid}", headers=h)
    assert g.status_code == 200
    data = g.json()
    assert data["tenant_id"] == "org_demo"
    assert len(data["steps"]) == 2
    assert data["steps"][1]["metadata"]["model"] == "gpt-4"


def test_tenant_mismatch(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_a",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
        "steps": [],
        "edges": [],
    }
    r = client.post("/v1/traces", json=body, headers={"X-Tenant-ID": "org_b"})
    assert r.status_code == 400


def test_duplicate_trace_id(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_demo"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201
    r2 = client.post("/v1/traces", json=body, headers=h)
    assert r2.status_code == 409
    assert "this tenant" in r2.json()["detail"]


def test_same_trace_id_allowed_across_tenants(client: TestClient) -> None:
    """Uniqueness is (tenant_id, trace_id); same UUID may exist for different tenants."""
    tid = uuid.uuid4()
    base = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [],
        "edges": [],
    }
    r_a = client.post(
        "/v1/traces",
        json={**base, "tenant_id": "org_a"},
        headers={"X-Tenant-ID": "org_a"},
    )
    r_b = client.post(
        "/v1/traces",
        json={**base, "tenant_id": "org_b"},
        headers={"X-Tenant-ID": "org_b"},
    )
    assert r_a.status_code == 201
    assert r_b.status_code == 201
    ga = client.get(f"/v1/traces/{tid}", headers={"X-Tenant-ID": "org_a"})
    gb = client.get(f"/v1/traces/{tid}", headers={"X-Tenant-ID": "org_b"})
    assert ga.json()["tenant_id"] == "org_a"
    assert gb.json()["tenant_id"] == "org_b"


def test_same_trace_id_conflict_across_environments(client: TestClient) -> None:
    """Uniqueness is per tenant+trace_id: second ingest with same id conflicts even if env differs."""
    tid = uuid.uuid4()
    base = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_demo"}
    r_prod = client.post("/v1/traces", json={**base, "environment": "prod"}, headers=h)
    r_stg = client.post("/v1/traces", json={**base, "environment": "staging"}, headers=h)
    assert r_prod.status_code == 201
    assert r_stg.status_code == 409

    g_default = client.get(f"/v1/traces/{tid}", headers=h)
    assert g_default.status_code == 200
    assert g_default.json()["environment"] == "prod"
    g_stg = client.get(f"/v1/traces/{tid}", headers=h, params={"environment": "staging"})
    assert g_stg.status_code == 404


def test_validation_duplicate_step_ids(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [
            {"step_id": "s1", "type": "retrieval", "input": {}, "output": {}},
            {"step_id": "s1", "type": "llm_call", "input": {}, "output": {}},
        ],
        "edges": [],
    }
    r = client.post("/v1/traces", json=body, headers={"X-Tenant-ID": "org_demo"})
    assert r.status_code == 422


def test_ingest_persists_trace_steps_index(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "error",
        "steps": [
            {
                "step_id": "s1",
                "type": "retrieval",
                "input": {"q": "hello"},
                "output": {"chunks": []},
                "error": None,
                "metadata": {},
            },
            {
                "step_id": "s2",
                "type": "tool_call",
                "parent_step_id": "s1",
                "input": {"tool": "search"},
                "output": {},
                "error": "timeout",
                "metadata": {"latency_ms": 1200},
            },
        ],
        "edges": [{"from_step_id": "s1", "to_step_id": "s2"}],
    }
    h = {"X-Tenant-ID": "org_demo"}
    r = client.post("/v1/traces", json=body, headers=h)
    assert r.status_code == 201

    async def count_steps() -> int:
        from app.db.engine import get_session
        from app.db.models import TraceStepRecord

        async with get_session() as session:
            q = select(func.count()).select_from(TraceStepRecord).where(
                TraceStepRecord.trace_id == str(tid),
                TraceStepRecord.tenant_id == "org_demo",
                TraceStepRecord.environment == "prod",
            )
            result = await session.execute(q)
            return int(result.scalar_one())

    assert asyncio.run(count_steps()) == 2
