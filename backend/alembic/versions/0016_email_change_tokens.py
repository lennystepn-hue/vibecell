"""email_change_tokens

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-25

Spec-6 Sprint A2: lets a signed-in user change their email. The token gets
mailed to the NEW address (so we re-prove control of the destination
mailbox), independently of the existing magic-link login token table.

A separate table keeps the security properties cleanly separated:
- magic_link_tokens: signin (any address with a pending token can be
  impersonated by clicking)
- email_change_tokens: change ownership of an EXISTING account (must be
  bound to a user_id and a target new_email)
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_change_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("new_email", sa.String(320), nullable=False, index=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False, index=True),
        sa.Column("consumed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("email_change_tokens")
