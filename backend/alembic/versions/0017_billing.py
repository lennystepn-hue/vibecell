"""billing: plans + subscriptions + stripe_events

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-25

Spec-6 Sprint B1. Three new tables:

* plans                — pricing tiers (v1: just 'pro' at €8.99/mo, 7d trial)
* subscriptions        — per-user state mirror of Stripe (1:1 with users)
* stripe_events        — webhook idempotency dedupe (append-only)

Pricing decision locked 2026-04-25:
  €8.99 / month, 7-day trial, no credit card during trial.
  See docs/superpowers/decisions/2026-04-25-pricing-model-locked.md
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("slug", sa.String(32), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("stripe_price_id", sa.String(64), nullable=True),
        sa.Column("monthly_price_eur_cents", sa.Integer, nullable=False),
        sa.Column("max_projects", sa.Integer, nullable=True),
        sa.Column(
            "ai_enrichment_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "session_retention_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("365"),
        ),
        sa.Column(
            "trial_period_days",
            sa.Integer,
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(26),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "plan_id",
            sa.String(26),
            sa.ForeignKey("plans.id"),
            nullable=False,
        ),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True, index=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("trial_ends_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("last_trial_email_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column(
            "processed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Seed the single 'pro' plan per the locked pricing decision.
    # ULID for the plan PK is stable so seeding is idempotent across CI runs.
    op.execute(
        """
        INSERT INTO plans (
            id, slug, name, stripe_price_id, monthly_price_eur_cents,
            max_projects, ai_enrichment_enabled, session_retention_days,
            trial_period_days
        ) VALUES (
            '01KQ2300000000PRO00000000P',
            'pro',
            'Pro',
            NULL,  -- set after Stripe Price is created via dashboard / setup script
            899,
            NULL,  -- unlimited
            true,
            365,
            7
        )
        """
    )


def downgrade() -> None:
    op.drop_table("stripe_events")
    op.drop_table("subscriptions")
    op.drop_table("plans")
