"""JWT auth path for server-issued tenant binding."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings


@pytest.fixture
def jwt_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "jwt_secret", "test-secret")
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_tenant_claim", "tenant_id")
    monkeypatch.setattr(settings, "jwt_issuer", "")
    monkeypatch.setattr(settings, "jwt_audience", "")
    monkeypatch.setattr(settings, "api_keys", {})


def _token(claims: dict) -> str:
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _minimal_trace(tenant_id: str) -> dict:
    tid = str(uuid.uuid4())
    return {
        "trace_id": tid,
        "tenant_id": tenant_id,
        "started_at": "2025-01-01T00:00:00Z",
        "status": "success",
        "steps": [],
    }


def test_ingest_with_jwt_bearer_resolves_tenant(client, jwt_auth) -> None:
    token = _token({"tenant_id": "tenant_from_jwt"})
    body = _minimal_trace("tenant_from_jwt")
    r = client.post("/v1/traces", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201


def test_jwt_missing_tenant_claim_401(client, jwt_auth) -> None:
    token = _token({"sub": "user_1"})
    body = _minimal_trace("tenant_from_jwt")
    r = client.post("/v1/traces", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert "tenant claim" in r.json()["detail"]


def test_jwt_tenant_mismatch_body_400(client, jwt_auth) -> None:
    token = _token({"tenant_id": "tenant_from_jwt"})
    body = _minimal_trace("other_tenant")
    r = client.post("/v1/traces", json=body, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
