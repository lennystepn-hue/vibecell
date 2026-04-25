"""project_screenshots

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-22

Stores auto-captured previews of each project's live site plus ship-event
screenshots and manual/moodboard uploads. Binary data lives on disk under a
volume; only the storage path is in Postgres.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_screenshots",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(20),
            nullable=False,
            comment="auto | ship | manual | moodboard",
        ),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("mime_type", sa.String(60), nullable=False, server_default="image/webp"),
        sa.Column("width", sa.Integer, nullable=True),
        sa.Column("height", sa.Integer, nullable=True),
        sa.Column(
            "captured_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "ship_id",
            sa.String(26),
            sa.ForeignKey("ships.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("source_url", sa.Text, nullable=True, comment="URL captured (for auto/ship)"),
    )
    op.create_index(
        "ix_project_screenshots_project_captured",
        "project_screenshots",
        ["project_id", "captured_at"],
    )
    op.create_index(
        "ix_project_screenshots_ship_id",
        "project_screenshots",
        ["ship_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_screenshots_ship_id", table_name="project_screenshots")
    op.drop_index("ix_project_screenshots_project_captured", table_name="project_screenshots")
    op.drop_table("project_screenshots")
