"""unique (tenant_id, trace_id) without environment

Revision ID: 20260324_0004
Revises: 20260323_0003
Create Date: 2026-03-24 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260324_0004"
down_revision = "20260323_0003"
branch_labels = None
depends_on = None


def _dedupe_sqlite(connection) -> None:
    """Remove duplicate rows keeping largest id per natural key (SQLite)."""
    for table, group_cols in [
        ("traces", "tenant_id, trace_id"),
        ("diagnoses", "tenant_id, trace_id"),
        ("ingest_jobs", "tenant_id, trace_id"),
    ]:
        connection.execute(
            sa.text(
                f"""
                DELETE FROM {table}
                WHERE id IN (
                  SELECT t1.id FROM {table} AS t1
                  INNER JOIN {table} AS t2
                    ON t1.tenant_id = t2.tenant_id
                    AND t1.trace_id = t2.trace_id
                    AND t1.id < t2.id
                )
                """
            )
        )
    connection.execute(
        sa.text(
            """
            DELETE FROM trace_steps
            WHERE id IN (
              SELECT t1.id FROM trace_steps AS t1
              INNER JOIN trace_steps AS t2
                ON t1.tenant_id = t2.tenant_id
                AND t1.trace_id = t2.trace_id
                AND t1.step_id = t2.step_id
                AND t1.id < t2.id
            )
            """
        )
    )


def _dedupe_postgresql(connection) -> None:
    _dedupe_sqlite(connection)


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        _dedupe_postgresql(bind)
    else:
        _dedupe_sqlite(bind)

    if dialect == "sqlite":
        with op.batch_alter_table("traces") as batch:
            batch.drop_constraint("uq_traces_tenant_env_trace", type_="unique")
            batch.create_unique_constraint("uq_traces_tenant_trace", ["tenant_id", "trace_id"])
        with op.batch_alter_table("diagnoses") as batch:
            batch.drop_constraint("uq_diagnoses_tenant_env_trace", type_="unique")
            batch.create_unique_constraint("uq_diagnoses_tenant_trace", ["tenant_id", "trace_id"])
        with op.batch_alter_table("trace_steps") as batch:
            batch.drop_constraint("uq_trace_steps_tenant_env_trace_step", type_="unique")
            batch.create_unique_constraint(
                "uq_trace_steps_tenant_trace_step",
                ["tenant_id", "trace_id", "step_id"],
            )
        with op.batch_alter_table("ingest_jobs") as batch:
            batch.drop_constraint("uq_ingest_jobs_tenant_env_trace", type_="unique")
            batch.create_unique_constraint("uq_ingest_jobs_tenant_trace", ["tenant_id", "trace_id"])
    else:
        op.drop_constraint("uq_traces_tenant_env_trace", "traces", type_="unique")
        op.create_unique_constraint("uq_traces_tenant_trace", "traces", ["tenant_id", "trace_id"])
        op.drop_constraint("uq_diagnoses_tenant_env_trace", "diagnoses", type_="unique")
        op.create_unique_constraint(
            "uq_diagnoses_tenant_trace", "diagnoses", ["tenant_id", "trace_id"]
        )
        op.drop_constraint("uq_trace_steps_tenant_env_trace_step", "trace_steps", type_="unique")
        op.create_unique_constraint(
            "uq_trace_steps_tenant_trace_step",
            "trace_steps",
            ["tenant_id", "trace_id", "step_id"],
        )
        op.drop_constraint("uq_ingest_jobs_tenant_env_trace", "ingest_jobs", type_="unique")
        op.create_unique_constraint(
            "uq_ingest_jobs_tenant_trace", "ingest_jobs", ["tenant_id", "trace_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("traces") as batch:
            batch.drop_constraint("uq_traces_tenant_trace", type_="unique")
            batch.create_unique_constraint(
                "uq_traces_tenant_env_trace", ["tenant_id", "environment", "trace_id"]
            )
        with op.batch_alter_table("diagnoses") as batch:
            batch.drop_constraint("uq_diagnoses_tenant_trace", type_="unique")
            batch.create_unique_constraint(
                "uq_diagnoses_tenant_env_trace", ["tenant_id", "environment", "trace_id"]
            )
        with op.batch_alter_table("trace_steps") as batch:
            batch.drop_constraint("uq_trace_steps_tenant_trace_step", type_="unique")
            batch.create_unique_constraint(
                "uq_trace_steps_tenant_env_trace_step",
                ["tenant_id", "environment", "trace_id", "step_id"],
            )
        with op.batch_alter_table("ingest_jobs") as batch:
            batch.drop_constraint("uq_ingest_jobs_tenant_trace", type_="unique")
            batch.create_unique_constraint(
                "uq_ingest_jobs_tenant_env_trace", ["tenant_id", "environment", "trace_id"]
            )
    else:
        op.drop_constraint("uq_traces_tenant_trace", "traces", type_="unique")
        op.create_unique_constraint(
            "uq_traces_tenant_env_trace", "traces", ["tenant_id", "environment", "trace_id"]
        )
        op.drop_constraint("uq_diagnoses_tenant_trace", "diagnoses", type_="unique")
        op.create_unique_constraint(
            "uq_diagnoses_tenant_env_trace",
            "diagnoses",
            ["tenant_id", "environment", "trace_id"],
        )
        op.drop_constraint("uq_trace_steps_tenant_trace_step", "trace_steps", type_="unique")
        op.create_unique_constraint(
            "uq_trace_steps_tenant_env_trace_step",
            "trace_steps",
            ["tenant_id", "environment", "trace_id", "step_id"],
        )
        op.drop_constraint("uq_ingest_jobs_tenant_trace", "ingest_jobs", type_="unique")
        op.create_unique_constraint(
            "uq_ingest_jobs_tenant_env_trace",
            "ingest_jobs",
            ["tenant_id", "environment", "trace_id"],
        )
