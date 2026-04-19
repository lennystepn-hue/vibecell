"""ship_loop

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("summary", sa.Text),
        sa.Column("files_touched", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("commits", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("next_step", sa.Text),
        sa.Column("source", sa.String(30), nullable=False),  # 'skill' | 'manual' | 'cli'
    )
    op.create_index("ix_sessions_project_id", "sessions", ["project_id"])
    op.create_index("ix_sessions_started_at", "sessions", ["started_at"])
    op.execute(
        "CREATE INDEX sessions_fts ON sessions USING gin "
        "(to_tsvector('english', coalesce(summary, '') || ' ' || coalesce(next_step, '')))"
    )

    # --- decisions ---
    op.create_table(
        "decisions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("title", sa.String(400), nullable=False),
        sa.Column("context", sa.Text),
        sa.Column("decision", sa.Text, nullable=False),
        sa.Column("consequences", sa.Text),
        sa.Column("reconsider_if", sa.Text),
    )
    op.create_index("ix_decisions_project_id", "decisions", ["project_id"])
    op.execute(
        "CREATE INDEX decisions_fts ON decisions USING gin "
        "(to_tsvector('english', title || ' ' || coalesce(decision, '') || ' ' || coalesce(context, '')))"
    )

    # --- ideas ---
    op.create_table(
        "ideas",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(26),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "captured_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("source", sa.String(30)),  # 'web' | 'ios' | 'email' | 'skill'
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="inbox",
        ),  # 'inbox'|'triaged'|'discarded'
    )
    op.create_index("ix_ideas_workspace_id", "ideas", ["workspace_id"])
    op.create_index("ix_ideas_project_id", "ideas", ["project_id"])
    op.create_index("ix_ideas_status", "ideas", ["status"])
    op.execute(
        "CREATE INDEX ideas_fts ON ideas USING gin (to_tsvector('english', body))"
    )

    # --- ships ---
    op.create_table(
        "ships",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "shipped_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("version", sa.String(50)),
        sa.Column("summary", sa.Text),
        sa.Column("changelog_md", sa.Text),
    )
    op.create_index("ix_ships_project_id", "ships", ["project_id"])

    # --- launches ---
    op.create_table(
        "launches",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "platform", sa.String(30), nullable=False
        ),  # 'ph'|'hn'|'x'|'reddit'|'newsletter'
        sa.Column("launched_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("url", sa.Text),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("ix_launches_project_id", "launches", ["project_id"])
    op.create_index("ix_launches_platform", "launches", ["platform"])

    # --- lifecycle events ---
    op.create_table(
        "lifecycle_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("detail", postgresql.JSONB),
    )
    op.create_index("ix_lifecycle_events_project_id", "lifecycle_events", ["project_id"])
    op.create_index("ix_lifecycle_events_kind", "lifecycle_events", ["kind"])

    # --- notes (singleton per project) ---
    op.create_table(
        "notes",
        sa.Column(
            "project_id",
            sa.String(26),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("markdown", sa.Text, nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute(
        "CREATE INDEX notes_fts ON notes USING gin (to_tsvector('english', markdown))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS notes_fts")
    op.drop_table("notes")
    op.drop_index("ix_lifecycle_events_kind", table_name="lifecycle_events")
    op.drop_index("ix_lifecycle_events_project_id", table_name="lifecycle_events")
    op.drop_table("lifecycle_events")
    op.drop_index("ix_launches_platform", table_name="launches")
    op.drop_index("ix_launches_project_id", table_name="launches")
    op.drop_table("launches")
    op.drop_index("ix_ships_project_id", table_name="ships")
    op.drop_table("ships")
    op.execute("DROP INDEX IF EXISTS ideas_fts")
    op.drop_index("ix_ideas_status", table_name="ideas")
    op.drop_index("ix_ideas_project_id", table_name="ideas")
    op.drop_index("ix_ideas_workspace_id", table_name="ideas")
    op.drop_table("ideas")
    op.execute("DROP INDEX IF EXISTS decisions_fts")
    op.drop_index("ix_decisions_project_id", table_name="decisions")
    op.drop_table("decisions")
    op.execute("DROP INDEX IF EXISTS sessions_fts")
    op.drop_index("ix_sessions_started_at", table_name="sessions")
    op.drop_index("ix_sessions_project_id", table_name="sessions")
    op.drop_table("sessions")
