from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _trace_payload(trace_id: str, tenant: str = "org_demo") -> dict:
    return {
        "schema_version": "1.0",
        "trace_id": trace_id,
        "tenant_id": tenant,
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [],
        "edges": [],
    }


def test_batch_ingest_mixed_results(client: TestClient) -> None:
    existing_id = str(uuid.uuid4())
    headers = {"X-Tenant-ID": "org_demo"}
    assert client.post("/v1/traces", json=_trace_payload(existing_id), headers=headers).status_code == 201

    new_id = str(uuid.uuid4())
    body = {
        "traces": [
            _trace_payload(new_id),
            _trace_payload(existing_id),  # conflict
            {"trace_id": "bad", "tenant_id": "org_demo"},  # invalid
        ]
    }

    r = client.post("/v1/traces/batch", json=body, headers=headers)
    assert r.status_code == 207
    data = r.json()
    assert data["total"] == 3
    assert data["accepted"] == 1
    assert data["queued"] == 0
    assert data["conflicts"] == 1
    assert data["invalid"] == 1
    assert data["queue_full"] == 0
    assert [x["status"] for x in data["items"]] == ["accepted", "conflict", "invalid"]
    assert data["items"][0]["http_status"] == 201
    assert data["items"][1]["error_code"] == "duplicate_trace_id"
    assert data["items"][2]["error_code"] == "validation_error"

    # accepted item is actually available
    g = client.get(f"/v1/traces/{new_id}", headers=headers)
    assert g.status_code == 200


def test_batch_ingest_rejects_oversized(client: TestClient) -> None:
    headers = {"X-Tenant-ID": "org_demo"}
    items = [_trace_payload(str(uuid.uuid4())) for _ in range(101)]
    r = client.post("/v1/traces/batch", json={"traces": items}, headers=headers)
    assert r.status_code == 400
    assert "batch too large" in r.json()["detail"]


def test_batch_ingest_all_success_returns_201(client: TestClient) -> None:
    headers = {"X-Tenant-ID": "org_demo"}
    body = {"traces": [_trace_payload(str(uuid.uuid4())), _trace_payload(str(uuid.uuid4()))]}
    r = client.post("/v1/traces/batch", json=body, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["accepted"] == 2
    assert data["queued"] == 0


def test_batch_ingest_marks_too_many_steps_item_invalid(client: TestClient) -> None:
    headers = {"X-Tenant-ID": "org_demo"}
    trace_id = str(uuid.uuid4())
    oversized = _trace_payload(trace_id)
    oversized["steps"] = [
        {"step_id": f"s{i}", "type": "tool_call", "input": {}, "output": {}, "metadata": {}}
        for i in range(1, 502)
    ]
    r = client.post("/v1/traces/batch", json={"traces": [oversized]}, headers=headers)
    assert r.status_code == 207
    data = r.json()
    assert data["invalid"] == 1
    assert data["items"][0]["status"] == "invalid"
    assert "too many steps" in (data["items"][0]["detail"] or "")


def test_batch_ingest_rejects_payload_too_large(client: TestClient) -> None:
    from app.config import settings

    previous = settings.ingest_max_payload_bytes
    settings.ingest_max_payload_bytes = 700
    try:
        headers = {"X-Tenant-ID": "org_demo"}
        trace_id = str(uuid.uuid4())
        oversized = _trace_payload(trace_id)
        oversized["steps"] = [
            {"step_id": "s1", "type": "tool_call", "input": {"payload": "x" * 5000}, "output": {}, "metadata": {}}
        ]
        r = client.post("/v1/traces/batch", json={"traces": [oversized]}, headers=headers)
        assert r.status_code == 413
        assert "too large" in r.json()["detail"]
    finally:
        settings.ingest_max_payload_bytes = previous


def test_batch_ingest_marks_oversized_step_field_invalid(client: TestClient) -> None:
    from app.config import settings

    prev_output = settings.ingest_max_step_output_bytes
    settings.ingest_max_step_output_bytes = 300
    try:
        headers = {"X-Tenant-ID": "org_demo"}
        t1 = _trace_payload(str(uuid.uuid4()))
        t2 = _trace_payload(str(uuid.uuid4()))
        t2["steps"] = [
            {
                "step_id": "s1",
                "type": "tool_call",
                "input": {},
                "output": {"blob": "x" * 2000},
                "metadata": {},
            }
        ]
        r = client.post("/v1/traces/batch", json={"traces": [t1, t2]}, headers=headers)
        assert r.status_code == 207
        data = r.json()
        assert data["accepted"] == 1
        assert data["invalid"] == 1
        assert data["items"][1]["status"] == "invalid"
        assert "steps[0].output exceeds" in (data["items"][1]["detail"] or "")
    finally:
        settings.ingest_max_step_output_bytes = prev_output
