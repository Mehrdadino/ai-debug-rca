"""add trace_steps table

Revision ID: 20260323_0002
Revises: 20260323_0001
Create Date: 2026-03-23 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260323_0002"
down_revision = "20260323_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trace_steps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=256), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False, server_default="prod"),
        sa.Column("step_id", sa.String(length=256), nullable=False),
        sa.Column("step_type", sa.String(length=64), nullable=False),
        sa.Column("parent_step_id", sa.String(length=256), nullable=True),
        sa.Column("has_error", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("trace_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("span_id", sa.String(length=256), nullable=True),
        sa.Column("traceparent", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "environment",
            "trace_id",
            "step_id",
            name="uq_trace_steps_tenant_env_trace_step",
        ),
    )
    op.create_index("ix_trace_steps_trace_id", "trace_steps", ["trace_id"], unique=False)
    op.create_index("ix_trace_steps_tenant_id", "trace_steps", ["tenant_id"], unique=False)
    op.create_index("ix_trace_steps_environment", "trace_steps", ["environment"], unique=False)
    op.create_index("ix_trace_steps_step_type", "trace_steps", ["step_type"], unique=False)
    op.create_index("ix_trace_steps_has_error", "trace_steps", ["has_error"], unique=False)
    op.create_index(
        "ix_trace_steps_trace_started_at",
        "trace_steps",
        ["trace_started_at"],
        unique=False,
    )
    op.create_index(
        "ix_trace_steps_tenant_env_trace",
        "trace_steps",
        ["tenant_id", "environment", "trace_id"],
        unique=False,
    )
    op.create_index(
        "ix_trace_steps_failures_window",
        "trace_steps",
        ["tenant_id", "environment", "step_type", "has_error", "trace_started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trace_steps_failures_window", table_name="trace_steps")
    op.drop_index("ix_trace_steps_tenant_env_trace", table_name="trace_steps")
    op.drop_index("ix_trace_steps_trace_started_at", table_name="trace_steps")
    op.drop_index("ix_trace_steps_has_error", table_name="trace_steps")
    op.drop_index("ix_trace_steps_step_type", table_name="trace_steps")
    op.drop_index("ix_trace_steps_environment", table_name="trace_steps")
    op.drop_index("ix_trace_steps_tenant_id", table_name="trace_steps")
    op.drop_index("ix_trace_steps_trace_id", table_name="trace_steps")
    op.drop_table("trace_steps")
