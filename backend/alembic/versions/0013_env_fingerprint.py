"""env_fingerprint on project_context

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-24

Stores a SHA-256 fingerprint of manifest files (package.json, pyproject.toml,
Dockerfile, docker-compose.yml, README.md, …) on `project_context`. Populated
by the MCP `vibecell_sync_repo` tool and read by `vibecell_check_env_drift`
so Claude can detect when the runtime environment changed between sessions
(new dep, new service, new env variable) and refresh the enrichment.

Shape of the JSON blob:
    {
      "files": { "package.json": "<sha256>", "pyproject.toml": "<sha256>", ... },
      "scanned_at": "2026-04-24T10:11:12Z",
      "local_path": "C:\\\\Users\\\\ender\\\\OneDrive\\\\Desktop\\\\Hangar"
    }

Default empty object so the column is non-null for existing rows.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_context",
        sa.Column(
            "env_fingerprint",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("project_context", "env_fingerprint")
