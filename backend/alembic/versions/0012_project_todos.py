"""project_todos

Revision ID: 0012
Revises: 0011
Create Date: 2026-04-22

Per-project task list. Ticked off by the user OR auto-ticked by Claude via
the MCP tool (`vibecell.todo_complete`). Grouped into free-form batches
(e.g. "Launch week", "Stripe integration") so a longer roadmap can be
sliced into checkpoints.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_todos",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("batch", sa.String(120), nullable=True, comment="optional free-form group label"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="open",
            comment="open | in_progress | done | cancelled",
        ),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "completed_by",
            sa.String(20),
            nullable=True,
            comment="user | claude | null when open",
        ),
        sa.Column("completion_note", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_project_todos_project_status_position",
        "project_todos",
        ["project_id", "status", "position"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_todos_project_status_position", table_name="project_todos")
    op.drop_table("project_todos")
