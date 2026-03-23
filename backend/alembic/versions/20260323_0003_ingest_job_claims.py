"""add ingest job claim fields

Revision ID: 20260323_0003
Revises: 20260323_0002
Create Date: 2026-03-23 01:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260323_0003"
down_revision = "20260323_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ingest_jobs",
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
    )
    op.add_column(
        "ingest_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("ingest_jobs", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ingest_jobs", sa.Column("claimed_by", sa.String(length=128), nullable=True))
    op.add_column(
        "ingest_jobs",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.add_column("ingest_jobs", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index("ix_ingest_jobs_status", "ingest_jobs", ["status"], unique=False)
    op.create_index("ix_ingest_jobs_available_at", "ingest_jobs", ["available_at"], unique=False)
    op.create_index(
        "ix_ingest_jobs_status_available_created",
        "ingest_jobs",
        ["status", "available_at", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingest_jobs_status_available_created", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_available_at", table_name="ingest_jobs")
    op.drop_index("ix_ingest_jobs_status", table_name="ingest_jobs")
    op.drop_column("ingest_jobs", "last_error")
    op.drop_column("ingest_jobs", "available_at")
    op.drop_column("ingest_jobs", "claimed_by")
    op.drop_column("ingest_jobs", "claimed_at")
    op.drop_column("ingest_jobs", "attempts")
    op.drop_column("ingest_jobs", "status")
