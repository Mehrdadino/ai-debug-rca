"""trace blob pointer + step_count

Revision ID: 20260324_0005
Revises: 20260324_0004
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260324_0005"
down_revision = "20260324_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "traces",
        sa.Column("step_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("traces", sa.Column("blob_key", sa.String(length=1024), nullable=True))
    op.add_column("traces", sa.Column("blob_etag", sa.String(length=128), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE traces SET step_count = (
                SELECT COUNT(*) FROM trace_steps AS s
                WHERE s.trace_id = traces.trace_id AND s.tenant_id = traces.tenant_id
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("traces", "blob_etag")
    op.drop_column("traces", "blob_key")
    op.drop_column("traces", "step_count")
