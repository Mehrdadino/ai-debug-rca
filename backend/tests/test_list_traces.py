from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _minimal_trace(
    tid: uuid.UUID,
    tenant: str,
    status: str = "success",
    *,
    started_at: str = "2025-01-15T10:00:00Z",
) -> dict:
    return {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": tenant,
        "started_at": started_at,
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
    assert data["items"][0]["environment"] == "prod"

    err_only = client.get("/v1/traces", headers=h, params={"status": "error"})
    assert err_only.status_code == 200
    assert len(err_only.json()["items"]) == 1
    assert err_only.json()["items"][0]["status"] == "error"


def test_list_traces_time_range_optional(client: TestClient) -> None:
    """started_at_from / started_at_to are optional; filter on trace run time (started_at)."""
    h = {"X-Tenant-ID": "org_time"}
    t_early = uuid.uuid4()
    t_mid = uuid.uuid4()
    t_late = uuid.uuid4()
    client.post(
        "/v1/traces",
        json=_minimal_trace(t_early, "org_time", started_at="2025-01-10T12:00:00Z"),
        headers=h,
    )
    client.post(
        "/v1/traces",
        json=_minimal_trace(t_mid, "org_time", started_at="2025-01-20T12:00:00Z"),
        headers=h,
    )
    client.post(
        "/v1/traces",
        json=_minimal_trace(t_late, "org_time", started_at="2025-01-30T12:00:00Z"),
        headers=h,
    )

    r = client.get(
        "/v1/traces",
        headers=h,
        params={
            "started_at_from": "2025-01-15T00:00:00Z",
            "started_at_to": "2025-01-25T23:59:59Z",
        },
    )
    assert r.status_code == 200
    ids = {item["trace_id"] for item in r.json()["items"]}
    assert str(t_mid) in ids
    assert str(t_early) not in ids
    assert str(t_late) not in ids

    bad = client.get(
        "/v1/traces",
        headers=h,
        params={
            "started_at_from": "2025-02-01T00:00:00Z",
            "started_at_to": "2025-01-01T00:00:00Z",
        },
    )
    assert bad.status_code == 400


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


def test_list_traces_environment_filter(client: TestClient) -> None:
    h = {"X-Tenant-ID": "org_env"}
    tid_prod = uuid.uuid4()
    tid_stg = uuid.uuid4()
    client.post(
        "/v1/traces",
        json={**_minimal_trace(tid_prod, "org_env"), "environment": "prod"},
        headers=h,
    )
    client.post(
        "/v1/traces",
        json={**_minimal_trace(tid_stg, "org_env"), "environment": "staging"},
        headers=h,
    )
    r = client.get("/v1/traces", headers=h, params={"environment": "staging"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["trace_id"] == str(tid_stg)
    assert items[0]["environment"] == "staging"
