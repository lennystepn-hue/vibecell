"""project_slug on mcp_audit_log

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-24

The activity feed used to show every workspace tool-call on every project's
detail page because mcp_audit_log only tracked workspace_id, not which
project the tool actually touched. We now stamp each row with the resolved
slug (or NULL for genuinely workspace-scoped tools like `vibecell_list`),
and the activity-feed reader filters by it.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_audit_log",
        sa.Column("project_slug", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_mcp_audit_log_workspace_project",
        "mcp_audit_log",
        ["workspace_id", "project_slug"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_audit_log_workspace_project", table_name="mcp_audit_log")
    op.drop_column("mcp_audit_log", "project_slug")
