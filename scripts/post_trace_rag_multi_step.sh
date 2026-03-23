#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

TRACE_ID="$(new_trace_id)"

BODY=$(cat <<EOF
{
  "schema_version": "1.0",
  "trace_id": "${TRACE_ID}",
  "tenant_id": "${TENANT}",
  "started_at": "2025-01-15T10:00:00Z",
  "ended_at": "2025-01-15T10:00:03Z",
  "status": "success",
  "correlation_ids": {
    "upstream_provider": "langfuse",
    "upstream_trace_id": "example-upstream-123"
  },
  "steps": [
    {
      "step_id": "s1",
      "type": "retrieval",
      "parent_step_id": null,
      "input": { "query": "What is the refund policy?" },
      "output": { "chunks": [ { "id": "doc-1", "text": "Refunds within 30 days." } ] },
      "error": null,
      "metadata": { "latency_ms": 45 }
    },
    {
      "step_id": "s2",
      "type": "llm_call",
      "parent_step_id": "s1",
      "input": { "messages": [ { "role": "user", "content": "What is the refund policy?" } ] },
      "output": { "text": "You can request a refund within 30 days of purchase." },
      "error": null,
      "metadata": {
        "latency_ms": 820,
        "model": "gpt-4",
        "tokens": { "input": 120, "output": 35 }
      }
    }
  ],
  "edges": []
}
EOF
)

echo "POST ${BASE_URL}/v1/traces (RAG: retrieval + LLM)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/v1/traces" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: ${TENANT}" \
  -d "${BODY}"
echo
echo "trace_id=${TRACE_ID}"
echo "GET trace:    curl -sS \"${BASE_URL}/v1/traces/${TRACE_ID}\" -H \"X-Tenant-ID: ${TENANT}\""
echo "GET diagnosis: curl -sS \"${BASE_URL}/v1/traces/${TRACE_ID}/diagnosis\" -H \"X-Tenant-ID: ${TENANT}\""
