"""Pytest: DB URL before imports; FastAPI TestClient + truncate between tests."""

from __future__ import annotations

import os
import re

os.environ.setdefault("RCA_DATABASE_URL", "postgresql+asyncpg://rca:rca@127.0.0.1:5433/rca_test")
# Deterministic tests: write in-request (201) instead of queued (202).
os.environ.setdefault("RCA_INGEST_SYNC", "1")


def _ensure_test_database_exists() -> None:
    import psycopg
    from psycopg import sql

    url = os.environ.get("RCA_DATABASE_URL", "")
    if "rca_test" not in url:
        return
    m = re.match(
        r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)",
        url,
    )
    if not m:
        return
    user, password, host, port, dbname = m.groups()
    admin = f"postgresql://{user}:{password}@{host}:{port}/postgres"
    conn = psycopg.connect(admin, connect_timeout=10)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
    if cur.fetchone() is None:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
    cur.close()
    conn.close()


_ensure_test_database_exists()

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _sync_truncate_test_db() -> None:
    """Sync TRUNCATE avoids asyncio.run() on a second loop (asyncpg vs TestClient)."""
    import psycopg

    url = os.environ.get("RCA_DATABASE_URL", "")
    m = re.match(
        r"postgresql\+asyncpg://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)",
        url,
    )
    if not m:
        raise RuntimeError("Tests expect RCA_DATABASE_URL=postgresql+asyncpg://...")
    user, password, host, port, dbname = m.groups()
    sync_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
    with psycopg.connect(sync_url) as conn:
        conn.execute(
            "TRUNCATE tenant_limits, traces, diagnoses, trace_steps, ingest_jobs "
            "RESTART IDENTITY CASCADE"
        )
        conn.commit()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _truncate_traces(client: TestClient) -> None:
    """Depends on client so lifespan + migrations ran before truncate."""
    _sync_truncate_test_db()


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    from app.config import settings
    from app.services.rate_limits import tenant_ingest_limiter

    settings.ingest_rate_limit_rps = 0
    settings.ingest_daily_trace_quota = 0
    settings.admin_token = ""
    settings.jwt_secret = ""
    settings.jwt_issuer = ""
    settings.jwt_audience = ""
    settings.jwt_tenant_claim = "tenant_id"
    tenant_ingest_limiter.reset()
