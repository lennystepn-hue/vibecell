"""admin role flag, TOTP 2FA, and admin audit log

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-03

Three pieces, all gated behind a multi-layer admin auth model:

1. `users.is_admin` BOOL — DB-level admin flag. The require_admin
   dependency demands BOTH this flag AND the user's email being in the
   HANGAR_ADMIN_EMAILS env list. Defense-in-depth: an attacker who
   manages to flip the bit via SQL injection still needs the env list,
   and an attacker who manages to override the env still needs the bit.

2. `users.totp_secret_enc` BYTEA + `users.totp_enabled_at` TIMESTAMP —
   per-user TOTP (RFC 6238) secret, encrypted at rest with the
   workspace-DEK pattern. Admin write actions require a fresh TOTP code
   (re-prompted server-side, not cached in session) so a stolen session
   cookie alone can't be used for admin writes.

3. `admin_audit_log` table — every admin write action lands here with
   actor user_id, action name, target (user_id / coupon_id / etc),
   payload (JSON), IP, user agent, timestamp. Separate from the
   existing audit table because (a) higher-sensitivity info, (b) longer
   retention, (c) admin-only readable.

Backfills `is_admin=true` for the founder email so the production admin
account works on first deploy without manual SQL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FOUNDER_EMAIL = "lennystepn@gmail.com"


def upgrade() -> None:
    # ── User columns ──────────────────────────────────────────────────────
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("totp_secret_enc", sa.Text(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("totp_enabled_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # ── Admin audit log ───────────────────────────────────────────────────
    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("action", sa.String(64), nullable=False, index=True),
        # Target type is opaque ("user", "coupon", "subscription", ...);
        # target_id is the relevant external id (Stripe coupon id, our
        # ULID, etc.). Both nullable for global actions like "exported_db".
        sa.Column("target_type", sa.String(32), nullable=True, index=True),
        sa.Column("target_id", sa.String(128), nullable=True, index=True),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("ip", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )

    # ── Backfill founder is_admin=true ────────────────────────────────────
    op.execute(
        f"""
        UPDATE users
           SET is_admin = true
         WHERE email = '{_FOUNDER_EMAIL}'
        """
    )


def downgrade() -> None:
    op.drop_table("admin_audit_log")
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_secret_enc")
    op.drop_column("users", "is_admin")
