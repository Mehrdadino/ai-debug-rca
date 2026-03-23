from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings


def _trace_payload(tenant: str) -> dict:
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


@pytest.fixture
def admin_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_token", "adm_test")


def test_admin_limits_api_disabled_without_token(client: TestClient) -> None:
    settings.admin_token = ""
    r = client.get("/v1/admin/tenants/org_demo/limits")
    assert r.status_code == 503


def test_admin_limits_upsert_and_get(client: TestClient, admin_token) -> None:
    h = {"X-Admin-Token": "adm_test"}
    put = client.put(
        "/v1/admin/tenants/org_limits/limits",
        json={"ingest_rate_limit_rps": 3, "ingest_daily_trace_quota": 10},
        headers=h,
    )
    assert put.status_code == 200
    assert put.json()["ingest_rate_limit_rps"] == 3
    get = client.get("/v1/admin/tenants/org_limits/limits", headers=h)
    assert get.status_code == 200
    assert get.json()["ingest_daily_trace_quota"] == 10


def test_tenant_limits_override_global_settings(client: TestClient, admin_token) -> None:
    settings.ingest_rate_limit_rps = 0
    settings.ingest_daily_trace_quota = 0
    admin_h = {"X-Admin-Token": "adm_test"}
    client.put(
        "/v1/admin/tenants/org_override/limits",
        json={"ingest_rate_limit_rps": 1, "ingest_daily_trace_quota": 1},
        headers=admin_h,
    )

    tenant_h = {"X-Tenant-ID": "org_override"}
    r1 = client.post("/v1/traces", json=_trace_payload("org_override"), headers=tenant_h)
    r2 = client.post("/v1/traces", json=_trace_payload("org_override"), headers=tenant_h)
    assert r1.status_code == 201
    assert r2.status_code == 429
