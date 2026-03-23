from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.config import settings


def _trace_payload(tenant: str = "org_demo") -> dict:
    return {
        "schema_version": "1.0",
        "trace_id": str(uuid.uuid4()),
        "tenant_id": tenant,
        "environment": "prod",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [],
        "edges": [],
    }


def test_ingest_rate_limit_single_requests(client: TestClient) -> None:
    settings.ingest_rate_limit_rps = 1
    h = {"X-Tenant-ID": "org_demo"}
    r1 = client.post("/v1/traces", json=_trace_payload(), headers=h)
    r2 = client.post("/v1/traces", json=_trace_payload(), headers=h)
    assert r1.status_code == 201
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers
    assert "rate limit" in r2.json()["detail"]


def test_ingest_daily_quota_batch(client: TestClient) -> None:
    settings.ingest_daily_trace_quota = 2
    h = {"X-Tenant-ID": "org_demo"}
    ok = client.post("/v1/traces/batch", json={"traces": [_trace_payload(), _trace_payload()]}, headers=h)
    blocked = client.post("/v1/traces", json=_trace_payload(), headers=h)
    assert ok.status_code == 201
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "daily ingest trace quota exceeded" in blocked.json()["detail"]


def test_ingest_quota_is_per_tenant(client: TestClient) -> None:
    settings.ingest_daily_trace_quota = 1
    a = {"X-Tenant-ID": "org_a"}
    b = {"X-Tenant-ID": "org_b"}
    assert client.post("/v1/traces", json=_trace_payload("org_a"), headers=a).status_code == 201
    assert client.post("/v1/traces", json=_trace_payload("org_b"), headers=b).status_code == 201
