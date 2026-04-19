"""groups

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_groups",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_project_groups_workspace_slug"),
    )
    op.create_index("ix_project_groups_workspace_id", "project_groups", ["workspace_id"])

    op.add_column(
        "projects",
        sa.Column("group_id", sa.String(26), sa.ForeignKey("project_groups.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("projects", sa.Column("position", sa.Integer, nullable=False, server_default="0"))
    op.create_index("ix_projects_group_id", "projects", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_projects_group_id", table_name="projects")
    op.drop_column("projects", "position")
    op.drop_column("projects", "group_id")
    op.drop_index("ix_project_groups_workspace_id", table_name="project_groups")
    op.drop_table("project_groups")
