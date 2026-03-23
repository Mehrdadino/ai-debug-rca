from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TraceRecord(Base):
    """Hot row + full normalized payload (S3-style blob deferred until needed)."""

    __tablename__ = "traces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "environment", "trace_id", name="uq_traces_tenant_env_trace"),
        Index("ix_traces_tenant_env_started_at", "tenant_id", "environment", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True, insert_default="prod")
    status: Mapped[str] = mapped_column(String(32), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
    )


class DiagnosisRecord(Base):
    """Derived diagnosis for a trace (rules v1). One row per trace."""

    __tablename__ = "diagnoses"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "environment",
            "trace_id",
            name="uq_diagnoses_tenant_env_trace",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True, insert_default="prod")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
    )


class IngestJobRecord(Base):
    """Durable async ingest backlog. Worker drains this table."""

    __tablename__ = "ingest_jobs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "environment",
            "trace_id",
            name="uq_ingest_jobs_tenant_env_trace",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True, insert_default="prod")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        index=True,
    )


class TenantLimitRecord(Base):
    """Per-tenant ingest policy controlled by admin APIs."""

    __tablename__ = "tenant_limits"

    tenant_id: Mapped[str] = mapped_column(String(256), primary_key=True)
    ingest_rate_limit_rps: Mapped[int] = mapped_column(insert_default=0)
    ingest_daily_trace_quota: Mapped[int] = mapped_column(insert_default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
