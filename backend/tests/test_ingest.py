from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone

import psycopg
from fastapi.testclient import TestClient


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
    assert data["steps"][0]["step_version"] == "1.0"
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

    url = os.environ["RCA_DATABASE_URL"]
    m = re.match(r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", url)
    assert m
    user, password, host, port, dbname = m.groups()
    sync_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    with psycopg.connect(sync_url) as conn:
        row = conn.execute(
            "SELECT COUNT(*), MIN(step_version), MAX(step_version) FROM trace_steps WHERE trace_id = %s AND tenant_id = %s AND environment = %s",
            (str(tid), "org_demo", "prod"),
        ).fetchone()
    assert row is not None and int(row[0]) == 2
    assert row[1] == "1.0"
    assert row[2] == "1.0"


def test_ingest_rejects_too_many_steps(client: TestClient) -> None:
    tid = uuid.uuid4()
    steps = [
        {
            "step_id": f"s{i}",
            "type": "tool_call",
            "input": {},
            "output": {},
            "metadata": {},
        }
        for i in range(1, 502)
    ]
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_demo",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": steps,
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_demo"}
    r = client.post("/v1/traces", json=body, headers=h)
    assert r.status_code == 422
    assert "too many steps" in r.json()["detail"]


def test_ingest_rejects_payload_too_large(client: TestClient) -> None:
    from app.config import settings

    previous = settings.ingest_max_payload_bytes
    settings.ingest_max_payload_bytes = 600
    try:
        tid = uuid.uuid4()
        body = {
            "schema_version": "1.0",
            "trace_id": str(tid),
            "tenant_id": "org_demo",
            "started_at": "2025-01-15T10:00:00Z",
            "status": "success",
            "steps": [
                {
                    "step_id": "s1",
                    "type": "tool_call",
                    "input": {"payload": "x" * 4000},
                    "output": {},
                    "metadata": {},
                }
            ],
            "edges": [],
        }
        h = {"X-Tenant-ID": "org_demo"}
        r = client.post("/v1/traces", json=body, headers=h)
        assert r.status_code == 413
        assert "too large" in r.json()["detail"]
    finally:
        settings.ingest_max_payload_bytes = previous


def test_ingest_rejects_oversized_step_metadata(client: TestClient) -> None:
    from app.config import settings

    prev_metadata = settings.ingest_max_step_metadata_bytes
    settings.ingest_max_step_metadata_bytes = 256
    try:
        tid = uuid.uuid4()
        body = {
            "schema_version": "1.0",
            "trace_id": str(tid),
            "tenant_id": "org_demo",
            "started_at": "2025-01-15T10:00:00Z",
            "status": "success",
            "steps": [
                {
                    "step_id": "s1",
                    "type": "tool_call",
                    "input": {},
                    "output": {},
                    "metadata": {"blob": "x" * 2000},
                }
            ],
            "edges": [],
        }
        r = client.post("/v1/traces", json=body, headers={"X-Tenant-ID": "org_demo"})
        assert r.status_code == 422
        assert "steps[0].metadata exceeds" in r.json()["detail"]
    finally:
        settings.ingest_max_step_metadata_bytes = prev_metadata
