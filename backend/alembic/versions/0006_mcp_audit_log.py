"""mcp audit log

Revision ID: 0006_mcp_audit_log
Revises: 0005_oauth
Create Date: 2026-04-20 00:00:01
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_audit_log",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(16), nullable=False),
    )
    op.create_index("ix_mcp_audit_client_called", "mcp_audit_log", ["client_id", "called_at"])
    op.create_index("ix_mcp_audit_workspace_tool", "mcp_audit_log", ["workspace_id", "tool_name"])


def downgrade() -> None:
    op.drop_table("mcp_audit_log")
