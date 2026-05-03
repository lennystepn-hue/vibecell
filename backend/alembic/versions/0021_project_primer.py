"""project primer markdown column

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-02

Long-form per-project README that the AI can fetch via the new
`vibecell_primer` MCP tool. The 30-line `pitch` column is for one-line
elevator copy; the 50-state ProjectContext fields are for here-and-now
state. Neither serves as the "give me the entire mental model of this
project" answer that an AI joining cold actually needs.

This column fills that gap — it's the project's CLAUDE.md / AGENTS.md /
README-for-AIs in one place, owned by the user, fetchable by the model.

TEXT (no length cap) so we don't have to migrate again when someone
writes a 40KB primer. Realistic ceiling is 50KB; nothing in the codepath
truncates so the dashboard textarea lets the user write whatever fits.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("primer_md", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "primer_md")
