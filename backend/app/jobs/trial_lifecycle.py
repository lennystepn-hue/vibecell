"""Hourly trial-state machine. Replaces the old trial_warnings.py.

The old job sent ONE email at T-2 days and never flipped status when
the trial actually expired — leading to "trialing" rows that lived
forever in the DB and (worse) users who lost access without an email
explaining what happened.

This job advances the state machine on every hourly tick:

    NULL                ─(at T-3)→  warned_3d  (email "ends in 3 days")
    warned_3d           ─(at T-1)→  warned_1d  (email "ends tomorrow")
    warned_1d / NULL    ─(at T-0)→  expired    (status='past_due',
                                                 email "trial ended",
                                                 stamp expired stage)

State only ever advances; the cron is fully idempotent and safe to run
as often as we like. We pick hourly so the worst-case timing skew on
expiration is 60 minutes — good enough for a SaaS trial, no need for
minute-by-minute work.

Subscriptions linked to Stripe (stripe_subscription_id != null) get
the same DB updates here. The Stripe-side trial expiry is Stripe's job
in that case — we simply mirror what's true server-side without
calling them on every tick (saves API budget + avoids drift loops).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.models import Subscription, User
from app.services.mailer import (
    send_trial_ended_email,
    send_trial_ending_email,
)

logger = logging.getLogger(__name__)


async def run_once() -> dict[str, int]:
    """Single tick — advance every subscription's trial state once.

    Returns a counter dict so the job log + future metrics can show
    "T-3 emails sent / T-1 emails sent / expirations stamped".
    """
    settings = get_settings()
    base_url = settings.base_url.rstrip("/")
    billing_url = f"{base_url}/settings/billing"

    now = datetime.now(UTC)
    in_3d = now + timedelta(days=3)
    in_1d = now + timedelta(days=1)

    counters: dict[str, int] = {"warn_3d": 0, "warn_1d": 0, "expired": 0}

    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Subscription, User)
                .join(User, User.id == Subscription.user_id)
                .where(Subscription.status == "trialing")
                .where(Subscription.trial_ends_at.is_not(None))
            )
        ).all()

        for sub, user in rows:
            if sub.trial_ends_at is None:
                continue

            ends_at = sub.trial_ends_at
            stage = sub.trial_email_stage  # NULL / warned_3d / warned_1d / expired

            # ── Stage T-0 (expired): flip status + send final email ─────
            # Even if we missed the warning emails (cron downtime, mail
            # outage), this is the one we MUST execute correctly so
            # status doesn't lie to the user/admin.
            if ends_at <= now and stage != "expired":
                sub.status = "past_due"
                sub.trial_email_stage = "expired"
                counters["expired"] += 1
                try:
                    await send_trial_ended_email(
                        to=user.email, billing_url=billing_url,
                    )
                except Exception as e:
                    # Email failure shouldn't block the status flip — the
                    # admin sees correct state, user can find the email
                    # later in their inbox even if delayed.
                    logger.warning(
                        "trial_lifecycle: trial_ended email failed user=%s: %s",
                        user.id, e,
                    )
                continue

            # ── Stage T-1: 1-day warning (only if not warned_1d/expired) ─
            if (
                ends_at <= in_1d
                and stage in (None, "warned_3d")
            ):
                try:
                    await send_trial_ending_email(
                        to=user.email, billing_url=billing_url,
                    )
                    sub.trial_email_stage = "warned_1d"
                    counters["warn_1d"] += 1
                except Exception as e:
                    logger.warning(
                        "trial_lifecycle: warn_1d email failed user=%s: %s",
                        user.id, e,
                    )
                continue

            # ── Stage T-3: 3-day warning (only if never warned) ──────────
            if ends_at <= in_3d and stage is None:
                try:
                    await send_trial_ending_email(
                        to=user.email, billing_url=billing_url,
                    )
                    sub.trial_email_stage = "warned_3d"
                    counters["warn_3d"] += 1
                except Exception as e:
                    logger.warning(
                        "trial_lifecycle: warn_3d email failed user=%s: %s",
                        user.id, e,
                    )

    if any(counters.values()):
        logger.info("trial_lifecycle: %s", counters)
    return counters


def schedule_trial_lifecycle_job(scheduler: AsyncIOScheduler) -> None:
    """Hourly trial-state machine. Replaces the old daily trial_warnings."""
    scheduler.add_job(
        run_once,
        "interval",
        hours=1,
        id="trial_lifecycle",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("trial_lifecycle: scheduled hourly")


# Backwards-compat shim for code that still imports the old name.
# Will be removed once all callers move to schedule_trial_lifecycle_job.
schedule_trial_warning_job = schedule_trial_lifecycle_job


# ---------------------------------------------------------------------------
# Stripe sync helper — used by admin actions that change trial / sub state.
# ---------------------------------------------------------------------------

async def sync_subscription_to_stripe(
    sub: Subscription, *, intent: str, value: Any | None = None,
) -> str | None:
    """Mirror a server-side state change onto Stripe when a stripe_subscription_id
    exists. Returns a short status string for audit logging; returns None
    when there's no Stripe linkage to sync (the action remains DB-only).

    Supported intents:
      • "extend_trial"  — value = new trial_ends_at (datetime). Pushes
                          Stripe's trial_end forward.
      • "cancel"        — sets cancel_at_period_end=true on Stripe.
      • "uncancel"      — clears cancel_at_period_end on Stripe.

    Failures here NEVER raise — admin actions still succeed locally if
    Stripe is unreachable. The audit log records "stripe_sync_failed"
    so the admin can see what didn't propagate.
    """
    import stripe

    settings = get_settings()
    if not sub.stripe_subscription_id or not settings.stripe_secret_key:
        return None
    stripe.api_key = settings.stripe_secret_key
    try:
        if intent == "extend_trial":
            assert isinstance(value, datetime)
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                trial_end=int(value.timestamp()),
                proration_behavior="none",
            )
            return "stripe_synced"
        if intent == "cancel":
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=True,
            )
            return "stripe_synced"
        if intent == "uncancel":
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=False,
            )
            return "stripe_synced"
    except Exception as e:
        logger.warning(
            "stripe sync failed sub=%s intent=%s: %s",
            sub.stripe_subscription_id, intent, e,
        )
        return "stripe_sync_failed"
    return None
