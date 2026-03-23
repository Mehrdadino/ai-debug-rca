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
  "status": "success",
  "steps": [
    {
      "step_id": "s1",
      "type": "retrieval",
      "input": { "query": "anything" },
      "output": { "chunks": [] },
      "error": null,
      "metadata": { "latency_ms": 12 }
    }
  ],
  "edges": []
}
EOF
)

echo "POST ${BASE_URL}/v1/traces (empty retrieval — expect diagnosis: empty_retrieval)"
curl -sS -w "\nHTTP %{http_code}\n" -X POST "${BASE_URL}/v1/traces" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: ${TENANT}" \
  -d "${BODY}"
echo
echo "trace_id=${TRACE_ID}"
echo "GET diagnosis: curl -sS \"${BASE_URL}/v1/traces/${TRACE_ID}/diagnosis\" -H \"X-Tenant-ID: ${TENANT}\""
