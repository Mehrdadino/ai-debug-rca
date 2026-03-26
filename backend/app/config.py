from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RCA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca"
    """Async SQLAlchemy URL. Local dev matches docker-compose.postgres.yml (port 5433)."""

    ingest_sync: bool = False
    """If True, write traces in the request handler (201). If False, enqueue and return 202."""

    ingest_queue_maxsize: int = 10_000
    """Max queued traces before POST returns 503 (only when ingest_sync is False)."""

    ingest_batch_max_size: int = 100
    """Maximum number of traces accepted by POST /v1/traces/batch."""

    ingest_max_steps_per_trace: int = 500
    """Maximum number of steps accepted for a single trace payload."""

    ingest_max_payload_bytes: int = 1_048_576
    """Hard max request body size (bytes) for ingest endpoints (/v1/traces*)."""

    ingest_max_step_error_bytes: int = 8_192
    """Maximum UTF-8 byte length for a single step `error` field."""

    ingest_max_step_metadata_bytes: int = 32_768
    """Maximum serialized JSON size (bytes) for a single step `metadata` object."""

    ingest_max_step_input_bytes: int = 65_536
    """Maximum serialized JSON size (bytes) for a single step `input` object."""

    ingest_max_step_output_bytes: int = 131_072
    """Maximum serialized JSON size (bytes) for a single step `output` object."""

    ingest_claim_timeout_seconds: int = 60
    """Claim lease timeout for processing jobs (stale claims become reclaimable)."""

    ingest_retry_delay_seconds: int = 5
    """Delay before retrying failed background ingest jobs."""

    ingest_max_attempts: int = 5
    """Max background attempts before marking ingest job dead."""

    ingest_rate_limit_rps: int = 0
    """Per-tenant ingest requests per second. 0 disables request-rate limiting."""

    ingest_daily_trace_quota: int = 0
    """Per-tenant accepted trace count per UTC day. 0 disables daily quota."""

    api_keys: dict[str, str] = Field(default_factory=dict)
    """Map API key string → tenant_id. When non-empty, requests must authenticate with
    Authorization: Bearer <key> or X-API-Key (X-Tenant-ID is not trusted for tenancy)."""

    jwt_secret: str = ""
    """HMAC secret for bearer JWT validation (HS256 by default). Empty disables JWT auth."""

    jwt_algorithm: str = "HS256"
    """JWT algorithm used for verification."""

    jwt_tenant_claim: str = "tenant_id"
    """JWT claim that carries tenant identifier."""

    jwt_issuer: str = ""
    """Optional expected JWT issuer."""

    jwt_audience: str = ""
    """Optional expected JWT audience."""

    admin_token: str = ""
    """Static admin token for privileged admin APIs (tenant limits management)."""

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_api_keys(cls, v: Any) -> dict[str, str]:
        if v is None or v == "":
            return {}
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return {}
            parsed = json.loads(s)
            if not isinstance(parsed, dict):
                raise ValueError("RCA_API_KEYS must be a JSON object")
            return {str(k): str(val) for k, val in parsed.items()}
        raise TypeError("RCA_API_KEYS must be a JSON object or dict")

    s3_bucket: str = ""
    """When non-empty, full trace JSON is stored here; `traces.payload` is empty and `blob_key` is set."""

    s3_endpoint_url: str = ""
    """Optional S3-compatible endpoint (e.g. http://127.0.0.1:9000 for MinIO). Empty uses default AWS."""

    s3_region: str = "us-east-1"

    s3_access_key_id: str = ""
    """Optional; when empty, boto3 uses standard AWS env/credential chain."""

    s3_secret_access_key: str = ""
    """Optional; when empty, boto3 uses standard AWS env/credential chain."""


settings = Settings()
