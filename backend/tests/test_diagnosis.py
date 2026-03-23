from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def test_diagnosis_step_error(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [
            {
                "step_id": "s1",
                "type": "llm_call",
                "input": {},
                "output": {},
                "error": "rate limited",
                "metadata": {},
            }
        ],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201

    r = client.get(f"/v1/traces/{tid}/diagnosis", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["primary_hypothesis"] == "step_error"
    assert d["confidence"] > 0.5
    assert any(e["rule_id"] == "step_error" for e in d["evidence"])


def test_diagnosis_no_rules(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [
            {
                "step_id": "s1",
                "type": "retrieval",
                "input": {},
                "output": {"chunks": [{"id": 1}]},
                "metadata": {},
            }
        ],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201
    d = client.get(f"/v1/traces/{tid}/diagnosis", headers=h).json()
    assert d["primary_hypothesis"] == "no_rules_fired"
    assert d["evidence"] == []
