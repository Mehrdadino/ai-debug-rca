from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
