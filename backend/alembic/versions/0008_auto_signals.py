"""auto signals — project health events + health summary

Revision ID: 0008_auto_signals
Revises: 0007
Create Date: 2026-04-20 00:00:03
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # project_health_events — raw probe results
    op.create_table(
        "project_health_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "probed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(16), nullable=False),  # up|down|timeout|error
        sa.Column("http_status_code", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_health_events_project_probed",
        "project_health_events",
        ["project_id", "probed_at"],
    )

    # project_health_summary — aggregated per-project summary
    op.create_table(
        "project_health_summary",
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("last_status", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("last_probed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("uptime_24h_pct", sa.Float, nullable=True),
        sa.Column("uptime_7d_pct", sa.Float, nullable=True),
        sa.Column("avg_latency_ms", sa.Integer, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("project_health_summary")
    op.drop_table("project_health_events")
