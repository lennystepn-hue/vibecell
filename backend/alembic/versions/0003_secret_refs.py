"""secret_refs

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_secret_refs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("reference", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "label", name="uq_project_secret_refs_project_label"),
    )
    op.create_index("ix_project_secret_refs_project_id", "project_secret_refs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_project_secret_refs_project_id", table_name="project_secret_refs")
    op.drop_table("project_secret_refs")
