"""Spec-6 Sprint B5: daily cron that emails trial users 2 days before
their trial expires. Idempotent via subscription.last_trial_email_at —
each user gets at most one warning per trial cycle.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import session_scope
from app.models import Subscription, User
from app.services.mailer import send_trial_ending_email

logger = logging.getLogger(__name__)


async def send_trial_ending_warnings() -> int:
    """Find subscriptions where trial_ends_at is within the next 2 days and
    no warning has been sent yet, mail them, stamp last_trial_email_at.

    Returns the number of emails sent (for the metric)."""
    settings = get_settings()

    now = datetime.now(UTC)
    cutoff = now + timedelta(days=2)

    sent = 0
    async with session_scope() as session:
        rows = (
            await session.execute(
                select(Subscription, User)
                .join(User, User.id == Subscription.user_id)
                .where(Subscription.status == "trialing")
                .where(Subscription.trial_ends_at.is_not(None))
                .where(Subscription.trial_ends_at <= cutoff)
                .where(Subscription.last_trial_email_at.is_(None))
            )
        ).all()

        for sub, user in rows:
            try:
                await send_trial_ending_email(
                    to=user.email,
                    billing_url=f"{settings.base_url.rstrip('/')}/settings/billing",
                )
                sub.last_trial_email_at = now
                sent += 1
            except Exception as e:
                # Log + continue — one bad mailbox shouldn't kill the whole batch
                logger.warning(
                    "trial-warning send failed for user_id=%s: %s", user.id, e
                )
        # session_scope auto-commits on clean exit

    if sent:
        logger.info("trial_warnings: emailed %d users", sent)
    return sent


def schedule_trial_warning_job(scheduler: object) -> None:
    """Wire the daily cron into APScheduler. Called from main.py lifespan."""
    scheduler.add_job(  # type: ignore[attr-defined]
        send_trial_ending_warnings,
        "cron",
        hour=9,
        minute=0,
        id="trial_warnings",
    )
