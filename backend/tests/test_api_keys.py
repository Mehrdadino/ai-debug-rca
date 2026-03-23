"""Server-issued tenant via RCA_API_KEYS (Bearer / X-API-Key)."""

from __future__ import annotations

import uuid

import pytest

from app.config import settings


@pytest.fixture
def api_key_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", {"sk_test_abc": "tenant_from_key"})


def _minimal_trace(tenant_id: str) -> dict:
    tid = str(uuid.uuid4())
    return {
        "trace_id": tid,
        "tenant_id": tenant_id,
        "started_at": "2025-01-01T00:00:00Z",
        "status": "success",
        "steps": [],
    }


def test_ingest_with_bearer_resolves_tenant(client, api_key_auth) -> None:
    body = _minimal_trace("tenant_from_key")
    r = client.post(
        "/v1/traces",
        json=body,
        headers={"Authorization": "Bearer sk_test_abc"},
    )
    assert r.status_code == 201
    tid = body["trace_id"]
    r2 = client.get(
        f"/v1/traces/{tid}",
        headers={"Authorization": "Bearer sk_test_abc"},
    )
    assert r2.status_code == 200
    assert r2.json()["tenant_id"] == "tenant_from_key"


def test_ingest_with_x_api_key(client, api_key_auth) -> None:
    body = _minimal_trace("tenant_from_key")
    r = client.post("/v1/traces", json=body, headers={"X-API-Key": "sk_test_abc"})
    assert r.status_code == 201


def test_wrong_key_401(client, api_key_auth) -> None:
    body = _minimal_trace("tenant_from_key")
    r = client.post(
        "/v1/traces",
        json=body,
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_header_tenant_ignored_without_bearer(client, api_key_auth) -> None:
    """When API keys are configured, X-Tenant-ID alone must not authenticate."""
    body = _minimal_trace("tenant_from_key")
    r = client.post(
        "/v1/traces",
        json=body,
        headers={"X-Tenant-ID": "tenant_from_key"},
    )
    assert r.status_code == 401


def test_tenant_mismatch_body_400(client, api_key_auth) -> None:
    body = _minimal_trace("other_tenant")
    r = client.post(
        "/v1/traces",
        json=body,
        headers={"Authorization": "Bearer sk_test_abc"},
    )
    assert r.status_code == 400
    assert "authenticated tenant" in r.json()["detail"]


def test_dev_mode_still_uses_x_tenant_id(client) -> None:
    """Default tests: no api_keys → X-Tenant-ID."""
    assert settings.api_keys == {}
    body = _minimal_trace("org_demo")
    r = client.post("/v1/traces", json=body, headers={"X-Tenant-ID": "org_demo"})
    assert r.status_code == 201
