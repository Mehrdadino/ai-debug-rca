from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _minimal_trace(tid: uuid.UUID, tenant: str, status: str = "success") -> dict:
    return {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": tenant,
        "started_at": "2025-01-15T10:00:00Z",
        "status": status,
        "steps": [{"step_id": "s1", "type": "retrieval", "input": {}, "output": {}}],
        "edges": [],
    }


def test_list_traces_pagination_and_filter(client: TestClient) -> None:
    h = {"X-Tenant-ID": "org_list"}
    t1 = uuid.uuid4()
    t2 = uuid.uuid4()
    t3 = uuid.uuid4()
    client.post("/v1/traces", json=_minimal_trace(t1, "org_list", "error"), headers=h)
    client.post("/v1/traces", json=_minimal_trace(t2, "org_list", "success"), headers=h)
    client.post("/v1/traces", json=_minimal_trace(t3, "org_list", "success"), headers=h)

    r = client.get("/v1/traces", headers=h, params={"limit": 2, "offset": 0})
    assert r.status_code == 200
    data = r.json()
    assert data["has_more"] is True
    assert len(data["items"]) == 2
    assert data["items"][0]["step_count"] == 1

    err_only = client.get("/v1/traces", headers=h, params={"status": "error"})
    assert err_only.status_code == 200
    assert len(err_only.json()["items"]) == 1
    assert err_only.json()["items"][0]["status"] == "error"


def test_list_traces_tenant_isolation(client: TestClient) -> None:
    tid = uuid.uuid4()
    client.post(
        "/v1/traces",
        json=_minimal_trace(tid, "org_a"),
        headers={"X-Tenant-ID": "org_a"},
    )
    r = client.get("/v1/traces", headers={"X-Tenant-ID": "org_b"})
    assert r.status_code == 200
    assert r.json()["items"] == []
