"""portfolio intel — portfolio_snapshot table

Revision ID: 0009_portfolio_intel
Revises: 0008
Create Date: 2026-04-20 00:00:04
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # portfolio_snapshot — append-only per-workspace snapshots
    op.create_table(
        "portfolio_snapshot",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("data", postgresql.JSONB, nullable=False),
    )
    op.create_index(
        "ix_portfolio_snapshot_workspace_generated",
        "portfolio_snapshot",
        ["workspace_id", "generated_at"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_snapshot")
