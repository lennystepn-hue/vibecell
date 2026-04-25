"""user.email_verified_at

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-25

Magic-link auth already implicitly verifies email at signup (the user proves
mailbox control by clicking the token). This column makes that fact a
queryable row instead of an inferred one — needed by Stripe customer creation
and the upcoming email-CHANGE flow.

Backfill rule for existing users: every account holder, by induction, has
already passed magic-link, so their email IS verified. Use users.created_at
as a proxy timestamp (we have no record of the actual click moment for
historical rows).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    # Backfill existing rows. Every existing user signed up via magic-link, so
    # their email is implicitly verified — use created_at as the proxy stamp.
    op.execute(
        'UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL'
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
