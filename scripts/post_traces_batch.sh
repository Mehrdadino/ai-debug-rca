#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/_common.sh
source "${SCRIPT_DIR}/_common.sh"

TRACE_ID_1="$(new_trace_id)"
TRACE_ID_2="$(new_trace_id)"
TRACE_ID_3="$(new_trace_id)"

BODY=$(cat <<EOF
{
  "traces": [
    {
      "schema_version": "1.0",
      "trace_id": "${TRACE_ID_1}",
      "tenant_id": "${TENANT}",
      "started_at": "2025-01-15T10:00:00Z",
      "status": "success",
      "steps": [],
      "edges": []
    },
    {
      "schema_version": "1.0",
      "trace_id": "${TRACE_ID_2}",
      "tenant_id": "${TENANT}",
      "started_at": "2025-01-15T10:00:01Z",
      "status": "error",
      "steps": [
        {
          "step_id": "s1",
          "type": "llm_call",
          "input": {},
          "output": {},
          "error": "simulated error",
          "metadata": { "latency_ms": 250 }
        }
      ],
      "edges": []
    },
    {
      "schema_version": "1.0",
      "trace_id": "${TRACE_ID_3}",
      "tenant_id": "${TENANT}",
      "started_at": "2025-01-15T10:00:02Z",
      "status": "success",
      "steps": [
        {
          "step_id": "s1",
          "type": "retrieval",
          "input": { "query": "example" },
          "output": { "chunks": [] },
          "metadata": { "latency_ms": 12 }
        }
      ],
      "edges": []
    }
  ]
}
EOF
)

echo "POST ${BASE_URL}/v1/traces/batch (3 traces)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/v1/traces/batch" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: ${TENANT}" \
  -d "${BODY}"
echo
echo "trace_ids=${TRACE_ID_1}, ${TRACE_ID_2}, ${TRACE_ID_3}"
echo "List traces: curl -sS \"${BASE_URL}/v1/traces?limit=10\" -H \"X-Tenant-ID: ${TENANT}\""
