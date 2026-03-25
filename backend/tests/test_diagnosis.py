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
    assert "step" in d["summary"].lower()
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
    assert "no diagnosis rules fired" in d["summary"].lower()
    assert d["evidence"] == []


def test_diagnosis_environment_lookup(client: TestClient) -> None:
    tid = uuid.uuid4()
    base = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "success",
        "steps": [{"step_id": "s1", "type": "retrieval", "input": {}, "output": {}}],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json={**base, "environment": "staging"}, headers=h).status_code == 201
    assert (
        client.get(f"/v1/traces/{tid}/diagnosis", headers=h).status_code == 404
    )  # default env=prod
    assert (
        client.get(
            f"/v1/traces/{tid}/diagnosis",
            headers=h,
            params={"environment": "staging"},
        ).status_code
        == 200
    )


def test_diagnosis_guardrail_block_is_primary(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "error",
        "steps": [
            {
                "step_id": "g1",
                "type": "guardrail",
                "input": {"policy": "pii"},
                "output": {},
                "error": "policy block: pii detected",
                "metadata": {},
            }
        ],
        "edges": [],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201
    d = client.get(f"/v1/traces/{tid}/diagnosis", headers=h).json()
    assert d["primary_hypothesis"] == "trace_status_error"
    assert d["summary"]
    assert "guardrail_block" in d["secondary_hypotheses"]
    assert any(e["rule_id"] == "guardrail_block" for e in d["evidence"])


def test_diagnosis_multiple_step_errors_rule_fires(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "error",
        "steps": [
            {
                "step_id": "s1",
                "type": "tool_call",
                "input": {"tool": "search"},
                "output": {},
                "error": "timeout",
                "metadata": {},
            },
            {
                "step_id": "s2",
                "type": "llm_call",
                "input": {"prompt": "x"},
                "output": {},
                "error": "rate limit",
                "metadata": {"latency_ms": 6100},
            },
        ],
        "edges": [{"from_step_id": "s1", "to_step_id": "s2"}],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201
    d = client.get(f"/v1/traces/{tid}/diagnosis", headers=h).json()
    assert d["primary_hypothesis"] == "trace_status_error"
    assert d["summary"]
    assert "multiple_step_errors" in d["secondary_hypotheses"]
    assert any(e["rule_id"] == "multiple_step_errors" for e in d["evidence"])


def test_diagnosis_empty_retrieval_then_error_rule_fires(client: TestClient) -> None:
    tid = uuid.uuid4()
    body = {
        "schema_version": "1.0",
        "trace_id": str(tid),
        "tenant_id": "org_x",
        "started_at": "2025-01-15T10:00:00Z",
        "status": "error",
        "steps": [
            {
                "step_id": "r1",
                "type": "retrieval",
                "input": {"query": "billing"},
                "output": {"chunks": []},
                "metadata": {},
            },
            {
                "step_id": "t1",
                "type": "tool_call",
                "parent_step_id": "r1",
                "input": {"tool": "calculator"},
                "output": {},
                "error": "invalid input",
                "metadata": {},
            },
        ],
        "edges": [{"from_step_id": "r1", "to_step_id": "t1"}],
    }
    h = {"X-Tenant-ID": "org_x"}
    assert client.post("/v1/traces", json=body, headers=h).status_code == 201
    d = client.get(f"/v1/traces/{tid}/diagnosis", headers=h).json()
    assert d["primary_hypothesis"] == "trace_status_error"
    assert d["summary"]
    assert "error_after_empty_retrieval" in d["secondary_hypotheses"]
    assert any(e["rule_id"] == "error_after_empty_retrieval" for e in d["evidence"])
