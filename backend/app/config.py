from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RCA_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    """Async SQLAlchemy URL. Default: local SQLite file under ./data/"""

    ingest_sync: bool = False
    """If True, write traces in the request handler (201). If False, enqueue and return 202."""

    ingest_queue_maxsize: int = 10_000
    """Max queued traces before POST returns 503 (only when ingest_sync is False)."""

    ingest_batch_max_size: int = 100
    """Maximum number of traces accepted by POST /v1/traces/batch."""

    ingest_rate_limit_rps: int = 0
    """Per-tenant ingest requests per second. 0 disables request-rate limiting."""

    ingest_daily_trace_quota: int = 0
    """Per-tenant accepted trace count per UTC day. 0 disables daily quota."""

    api_keys: dict[str, str] = Field(default_factory=dict)
    """Map API key string → tenant_id. When non-empty, requests must authenticate with
    Authorization: Bearer <key> or X-API-Key (X-Tenant-ID is not trusted for tenancy)."""

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

    @property
    def database_path(self) -> Optional[Path]:
        if self.database_url.startswith("sqlite+aiosqlite:///./"):
            return Path(self.database_url.removeprefix("sqlite+aiosqlite:///./"))
        return None


settings = Settings()
