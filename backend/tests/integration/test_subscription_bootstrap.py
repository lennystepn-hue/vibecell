"""Spec-6 Sprint B1: signup auto-creates a Subscription pointing at the
seeded 'pro' plan with status='trialing'."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Plan, Subscription, User
from app.services.login import issue_magic_link, verify_magic_link

pytestmark = pytest.mark.integration


async def test_pro_plan_seeded(session: AsyncSession) -> None:
    """The migration seeds exactly one plan (slug=pro, 899 cents, 7d trial)."""
    plans = (await session.execute(select(Plan))).scalars().all()
    assert len(plans) == 1
    pro = plans[0]
    assert pro.slug == "pro"
    assert pro.monthly_price_eur_cents == 899
    assert pro.trial_period_days == 7
    assert pro.ai_enrichment_enabled is True
    assert pro.max_projects is None  # unlimited


async def test_signup_creates_trialing_subscription(session: AsyncSession) -> None:
    raw = await issue_magic_link(session, email="trial-b1@example.com")
    await session.commit()
    await verify_magic_link(session, raw_token=raw)
    await session.commit()

    user = (
        await session.execute(select(User).where(User.email == "trial-b1@example.com"))
    ).scalar_one()

    sub = (
        await session.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one()

    assert sub.status == "trialing"
    assert sub.trial_ends_at is not None
    # Trial ends ~7 days from now
    delta = sub.trial_ends_at - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta < timedelta(days=7, hours=1)
    assert sub.stripe_customer_id is None  # not yet through Checkout
    assert sub.cancel_at_period_end is False
