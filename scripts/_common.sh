#!/usr/bin/env bash
# Shared defaults for example scripts (source from each script).
export BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
export TENANT="${TENANT:-org_demo}"

new_trace_id() {
  python3 -c "import uuid; print(uuid.uuid4())"
}
