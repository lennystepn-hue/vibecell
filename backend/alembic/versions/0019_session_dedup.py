"""dedupe duplicate sessions created by cron + manual log race

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-27

Spec-6 hotfix.

Symptom: the dashboard's `// SESSIONS` list displayed every recent commit
twice — once as `source='skill'` (Claude's vibecell_log_session call) and
once as `source='github'` (the commit_sync cron picking up the same SHA).

Root cause: the cron's dedup looked for the SHA inside `commits[].sha`,
but skill-source rows often had `commits=[]` (the SKILL doesn't always
include the SHA when summarising). So the cron treated the commit as
unlogged and inserted a parallel row.

The forward fix lives in app/jobs/commit_sync.py (`_link_or_skip_existing`):
the cron now also checks for a recent same-summary skill row and links the
SHA into its commits[] instead of inserting. This migration cleans up the
existing duplicates that landed before that fix.

Strategy: for each pair of sessions on the same project where one is
source='github' and another isn't, with identical summary, started within
30 minutes — keep the non-github row (it has the human-curated context),
and merge the github row's SHA into its commits[] before deleting the
github copy. Forensically reversible via the `deleted_session_log` audit
table that audit_listener already populates.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Append the github row's SHA into the matching skill row's commits[].
    #    Use jsonb_insert so we don't clobber any other commits already there.
    #    `||` performs JSONB array concat, which is what we want.
    op.execute(
        """
        WITH dup_pairs AS (
            SELECT
                gh.id AS gh_id,
                sk.id AS sk_id,
                gh.commits AS gh_commits
            FROM sessions gh
            JOIN sessions sk
              ON sk.project_id = gh.project_id
             AND sk.summary IS NOT DISTINCT FROM gh.summary
             AND sk.id <> gh.id
             AND sk.source <> 'github'
             AND ABS(EXTRACT(EPOCH FROM (sk.started_at - gh.started_at))) <= 1800
            WHERE gh.source = 'github'
        )
        UPDATE sessions s
           SET commits = COALESCE(s.commits, '[]'::jsonb) || dp.gh_commits
          FROM dup_pairs dp
         WHERE s.id = dp.sk_id
           AND dp.gh_commits IS NOT NULL
           AND jsonb_typeof(dp.gh_commits) = 'array'
        """
    )

    # 2. Delete the github duplicates we just merged.
    op.execute(
        """
        DELETE FROM sessions gh
        USING sessions sk
        WHERE sk.project_id = gh.project_id
          AND sk.summary IS NOT DISTINCT FROM gh.summary
          AND sk.id <> gh.id
          AND sk.source <> 'github'
          AND gh.source = 'github'
          AND ABS(EXTRACT(EPOCH FROM (sk.started_at - gh.started_at))) <= 1800
        """
    )


def downgrade() -> None:
    # No-op: forward-only cleanup. We can't reconstruct the deleted github
    # session rows since their content has been merged into the kept row.
    pass
