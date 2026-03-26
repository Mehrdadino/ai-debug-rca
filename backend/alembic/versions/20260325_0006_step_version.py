"""add step_version to trace_steps

Revision ID: 20260325_0006
Revises: 20260324_0005
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260325_0006"
down_revision = "20260324_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "trace_steps",
        sa.Column("step_version", sa.String(length=16), nullable=False, server_default="1.0"),
    )


def downgrade() -> None:
    op.drop_column("trace_steps", "step_version")
