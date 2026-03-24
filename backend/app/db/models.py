from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TraceRecord(Base):
    """Hot row + full normalized payload (S3-style blob deferred until needed)."""

    __tablename__ = "traces"
    __table_args__ = (
        UniqueConstraint("tenant_id", "trace_id", name="uq_traces_tenant_trace"),
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
            "trace_id",
            name="uq_diagnoses_tenant_trace",
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


class TraceStepRecord(Base):
    """Step-level index for fast cross-trace queries."""

    __tablename__ = "trace_steps"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "trace_id",
            "step_id",
            name="uq_trace_steps_tenant_trace_step",
        ),
        Index("ix_trace_steps_tenant_env_trace", "tenant_id", "environment", "trace_id"),
        Index(
            "ix_trace_steps_failures_window",
            "tenant_id",
            "environment",
            "step_type",
            "has_error",
            "trace_started_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True, insert_default="prod")
    step_id: Mapped[str] = mapped_column(String(256))
    step_type: Mapped[str] = mapped_column(String(64), index=True)
    parent_step_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    has_error: Mapped[bool] = mapped_column(Boolean, index=True, insert_default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    output_payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column("metadata", JSON)
    span_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    traceparent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
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
            "trace_id",
            name="uq_ingest_jobs_tenant_trace",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(256), index=True)
    environment: Mapped[str] = mapped_column(String(32), index=True, insert_default="prod")
    status: Mapped[str] = mapped_column(String(32), index=True, insert_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, insert_default=0)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
