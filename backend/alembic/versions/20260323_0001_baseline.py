"""baseline schema

Revision ID: 20260323_0001
Revises:
Create Date: 2026-03-23 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260323_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_limits",
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("ingest_rate_limit_rps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingest_daily_trace_quota", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_table(
        "traces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="prod"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "environment", "trace_id", name="uq_traces_tenant_env_trace"),
    )
    op.create_index("ix_traces_trace_id", "traces", ["trace_id"], unique=False)
    op.create_index("ix_traces_tenant_id", "traces", ["tenant_id"], unique=False)
    op.create_index("ix_traces_environment", "traces", ["environment"], unique=False)
    op.create_index("ix_traces_status", "traces", ["status"], unique=False)
    op.create_index("ix_traces_started_at", "traces", ["started_at"], unique=False)
    op.create_index(
        "ix_traces_tenant_env_started_at",
        "traces",
        ["tenant_id", "environment", "started_at"],
        unique=False,
    )

    op.create_table(
        "diagnoses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="prod"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "environment",
            "trace_id",
            name="uq_diagnoses_tenant_env_trace",
        ),
    )
    op.create_index("ix_diagnoses_trace_id", "diagnoses", ["trace_id"], unique=False)
    op.create_index("ix_diagnoses_tenant_id", "diagnoses", ["tenant_id"], unique=False)
    op.create_index("ix_diagnoses_environment", "diagnoses", ["environment"], unique=False)

    op.create_table(
        "ingest_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="prod"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "environment",
            "trace_id",
            name="uq_ingest_jobs_tenant_env_trace",
        ),
    )
    op.create_index("ix_ingest_jobs_trace_id", "ingest_jobs", ["trace_id"], unique=False)
    op.create_index("ix_ingest_jobs_tenant_id", "ingest_jobs", ["tenant_id"], unique=False)
    op.create_index("ix_ingest_jobs_environment", "ingest_jobs", ["environment"], unique=False)
    op.create_index("ix_ingest_jobs_created_at", "ingest_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_created_at", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_environment", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_tenant_id", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_trace_id", table_name="ingest_jobs")
    op.drop_table("ingest_jobs")

    op.drop_index("ix_diagnoses_environment", table_name="diagnoses")
    op.drop_index("ix_diagnoses_tenant_id", table_name="diagnoses")
    op.drop_index("ix_diagnoses_trace_id", table_name="diagnoses")
    op.drop_table("diagnoses")

    op.drop_index("ix_traces_tenant_env_started_at", table_name="traces")
    op.drop_index("ix_traces_started_at", table_name="traces")
    op.drop_index("ix_traces_status", table_name="traces")
    op.drop_index("ix_traces_environment", table_name="traces")
    op.drop_index("ix_traces_tenant_id", table_name="traces")
    op.drop_index("ix_traces_trace_id", table_name="traces")
    op.drop_table("traces")

    op.drop_table("tenant_limits")
