"""aggressive same-source session dedup

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-27

Spec-6 hotfix follow-up.

0019 only handled cross-source dups (github + skill pair). The live data
also has same-source pairs — two github rows for the same SHA, two skill
rows for the same summary — caused by historical races in the cron and
the SKILL's auto-logging behaviour.

This migration: for every group of sessions with identical
(project_id, summary, source) where started_at is within 60 seconds,
keep the row with the smallest id (ULIDs are time-ordered, so the
oldest one wins) and delete the rest. Since the commits[] arrays in
these dup-pairs are byte-identical (verified pre-migration), no merge
step is needed.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Delete every session row that has an OLDER sibling with the same
    # (project_id, summary, source) within a 60-second window. Older = smaller
    # ULID, since ULIDs encode the creation timestamp in the high bits.
    op.execute(
        """
        DELETE FROM sessions s1
        USING sessions s2
        WHERE s2.id < s1.id
          AND s2.project_id = s1.project_id
          AND s2.summary IS NOT DISTINCT FROM s1.summary
          AND s2.source = s1.source
          AND ABS(EXTRACT(EPOCH FROM (s2.started_at - s1.started_at))) <= 60
        """
    )


def downgrade() -> None:
    # Forward-only — the deleted rows had identical content to the kept ones,
    # so there's nothing to reconstruct.
    pass
