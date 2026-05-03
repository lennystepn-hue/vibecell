"""Spec-6 Sprint B1: plan + subscription + idempotency models.

The DB is the source of truth for "is this user paying?". Stripe is the
upstream that pushes updates via webhook; we mirror state here so all our
code can branch on `subscription.status` without round-tripping to Stripe.

Design:
- Single `pro` plan seeded by alembic 0017's data step (per pricing
  decision 2026-04-25: €8.99/mo, 7-day trial, no CC during trial).
  No `free` tier today — leaving the table flexible to add one later.
- Subscription is 1:1 with User (unique FK) — workspaces don't pay,
  users do. If we ever introduce team-billing, this becomes 1:1 with
  Workspace and User.subscription_id moves to Workspace.
- StripeEvent is a dedupe table — Stripe retries webhooks aggressively,
  we don't want to double-apply state changes.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, ulid_pk


class Plan(Base):
    """A pricing tier offered to users. v1: just `pro`."""

    __tablename__ = "plans"

    id: Mapped[str] = ulid_pk()
    slug: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    # Stripe Price ID (price_...) — null only for non-billable plans (e.g. a
    # future "free" tier). Today's only plan ('pro') has one.
    stripe_price_id: Mapped[str | None] = mapped_column(String(64))
    monthly_price_eur_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # null = unlimited; v1 'pro' is unlimited
    max_projects: Mapped[int | None] = mapped_column(Integer)
    ai_enrichment_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    session_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="365"
    )
    # Days of free trial granted on signup. 0 = no trial (charged immediately).
    trial_period_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )


class Subscription(Base, TimestampMixin):
    """Per-user billing state. Auto-created on first signup with status =
    'trialing' pointing at the default plan. Updated by Stripe webhooks
    afterwards."""

    __tablename__ = "subscriptions"

    id: Mapped[str] = ulid_pk()
    user_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("plans.id"), nullable=False
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(
        String(64), index=True
    )
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64))
    # Stripe values: 'trialing' | 'active' | 'past_due' | 'canceled' |
    # 'incomplete' | 'incomplete_expired' | 'paused' | 'unpaid'
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trial_ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Trial-lifecycle state machine marker. NULL initially, advances
    # through "warned_3d" → "warned_1d" → "expired" as the hourly
    # trial_lifecycle cron runs. Only ever advances; idempotent.
    trial_email_stage: Mapped[str | None] = mapped_column(String(20))


class StripeEvent(Base):
    """Dedupe table — Stripe webhooks retry; we record processed event IDs
    so we never apply the same state change twice. Rows are append-only."""

    __tablename__ = "stripe_events"

    # Stripe's evt_xxx ID — natural primary key, unique by definition
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
