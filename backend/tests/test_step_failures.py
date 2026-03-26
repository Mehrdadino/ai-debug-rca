from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _trace_with_step(
    *,
    tenant_id: str,
    trace_id: str,
    started_at: str,
    step_type: str,
    error: str | None,
    environment: str = "prod",
) -> dict:
    return {
        "schema_version": "1.0",
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "environment": environment,
        "started_at": started_at,
        "status": "error" if error else "success",
        "steps": [
            {
                "step_id": "s1",
                "type": step_type,
                "input": {},
                "output": {},
                "error": error,
                "metadata": {},
            }
        ],
        "edges": [],
    }


def test_ingest_accepts_non_enum_step_type(client: TestClient) -> None:
    tid = str(uuid.uuid4())
    body = _trace_with_step(
        tenant_id="org_steps",
        trace_id=tid,
        started_at=datetime.now(timezone.utc).isoformat(),
        step_type="custom_tool_v2",
        error="boom",
    )
    r = client.post("/v1/traces", json=body, headers={"X-Tenant-ID": "org_steps"})
    assert r.status_code == 201


def test_steps_endpoint_filters_by_type_error_and_time(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    recent_tool = _trace_with_step(
        tenant_id="org_steps",
        trace_id=str(uuid.uuid4()),
        started_at=(now - timedelta(days=2)).isoformat(),
        step_type="tool_call",
        error="timeout",
    )
    recent_other = _trace_with_step(
        tenant_id="org_steps",
        trace_id=str(uuid.uuid4()),
        started_at=(now - timedelta(days=1)).isoformat(),
        step_type="custom_tool_v2",
        error="failed",
    )
    old_tool = _trace_with_step(
        tenant_id="org_steps",
        trace_id=str(uuid.uuid4()),
        started_at=(now - timedelta(days=10)).isoformat(),
        step_type="tool_call",
        error="too_old",
    )

    h = {"X-Tenant-ID": "org_steps"}
    assert client.post("/v1/traces", json=recent_tool, headers=h).status_code == 201
    assert client.post("/v1/traces", json=recent_other, headers=h).status_code == 201
    assert client.post("/v1/traces", json=old_tool, headers=h).status_code == 201

    filtered = client.get(
        "/v1/traces/steps",
        headers=h,
        params={"step_type": "tool_call", "has_error": "true", "days": 7},
    )
    assert filtered.status_code == 200
    data = filtered.json()
    assert data["items"]
    assert all(item["step_type"] == "tool_call" for item in data["items"])
    assert all(item["error"] for item in data["items"])
    assert len(data["items"]) == 1

    all_recent = client.get(
        "/v1/traces/steps",
        headers=h,
        params={"days": 7},
    )
    assert all_recent.status_code == 200
    all_data = all_recent.json()
    assert len(all_data["items"]) == 2


def test_steps_failures_alias_is_back_compatible(client: TestClient) -> None:
    now = datetime.now(timezone.utc)
    payload = _trace_with_step(
        tenant_id="org_steps",
        trace_id=str(uuid.uuid4()),
        started_at=(now - timedelta(days=1)).isoformat(),
        step_type="tool_call",
        error="timeout",
    )
    h = {"X-Tenant-ID": "org_steps"}
    assert client.post("/v1/traces", json=payload, headers=h).status_code == 201

    r = client.get("/v1/traces/steps/failures", headers=h, params={"days": 7})
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["error"] == "timeout"
    assert data["items"][0]["step_version"] == "1.0"
