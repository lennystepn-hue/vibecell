"""multi-stage trial lifecycle + backfill expired trials

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-03

The pre-0023 trial flow was broken in two ways:

  1. Single email at T-2 days only — no warning at T-1 or T-0, no email
     when the trial actually expires.
  2. Status NEVER auto-flipped — once `trial_ends_at` passed, the row
     stayed `status='trialing'` forever (Stripe doesn't tell us either,
     since users have no payment method during the trial). Result: the
     dashboard shows "trialing" indefinitely + the user never knows
     they're actually past_due.

Fix: replace `last_trial_email_at` (single-stage) with `trial_email_stage`
(NULL / "warned_3d" / "warned_1d" / "expired") so the hourly trial-
lifecycle job can advance state safely without re-sending emails.

Backfill: any subscription still `trialing` with `trial_ends_at < now()`
gets flipped to `past_due` immediately. The user got a buggy experience
once; we fix it forward.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── Replace last_trial_email_at with trial_email_stage ──────────────
    # Drop the boolean-ish single-shot column, add a string stage marker.
    # Old data is discarded — the new state machine starts fresh per
    # subscription (anyone who got a T-2 warning under the old code will
    # get the new T-1 + T-0 emails, which is closer to right behaviour
    # than skipping them entirely).
    op.drop_column("subscriptions", "last_trial_email_at")
    op.add_column(
        "subscriptions",
        sa.Column("trial_email_stage", sa.String(20), nullable=True),
    )

    # ── Backfill: flip currently-expired trials to past_due ─────────────
    # The cron will catch up correctly going forward, but anyone whose
    # trial expired before this migration deploys deserves an immediate
    # fix so the admin dashboard stops misreporting.
    op.execute(
        """
        UPDATE subscriptions
           SET status = 'past_due',
               trial_email_stage = 'expired'
         WHERE status = 'trialing'
           AND trial_ends_at IS NOT NULL
           AND trial_ends_at < now()
        """
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "trial_email_stage")
    op.add_column(
        "subscriptions",
        sa.Column(
            "last_trial_email_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
