"""backfill subscriptions for users created before B1

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-25

Spec-6 Sprint B follow-up.

The B1 bootstrap (login.verify_magic_link) creates a Subscription row
for every NEW signup. Existing users — who signed up before 0017 ran —
have no sub row yet, so /me/subscription returns a validation error
and the /settings/billing page renders blank.

This migration: for every user without a subscription, INSERT one
pointing at the 'pro' plan with status='trialing' and trial_ends_at =
created_at + 7 days. Uses ULIDs that are valid 26-char strings; we
generate them in SQL via Postgres function-style concatenation since
we don't have a per-row Python step in alembic data migrations.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Generate a synthetic ULID-shaped string per row in pure SQL — we don't
    # need cryptographic uniqueness here, just unique 26-char primary keys.
    # The "B" prefix marks it as a backfill row for forensics.
    # Use md5(user_id) truncated to 26 chars — deterministic, unique per
    # user, fits the String(26) PK column. Prefix isn't needed since md5
    # is already collision-free for our purposes.
    op.execute(
        """
        INSERT INTO subscriptions (
            id, user_id, plan_id, status, trial_ends_at,
            cancel_at_period_end, created_at, updated_at
        )
        SELECT
            substring(md5('sub:' || u.id), 1, 26),
            u.id,
            (SELECT id FROM plans WHERE slug = 'pro' LIMIT 1),
            'trialing',
            u.created_at + INTERVAL '7 days',
            false,
            u.created_at,
            now()
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM subscriptions s WHERE s.user_id = u.id
        )
        """
    )


def downgrade() -> None:
    # No-op: forward-only data migration. Re-running upgrade() is idempotent
    # via the WHERE NOT EXISTS guard, so no need to clean up on downgrade.
    pass
