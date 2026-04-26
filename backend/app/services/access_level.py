"""Spec-6 — central derivation of "what access does this user have right now".

Every other layer (MCP dispatcher, REST plan-gate, cron job filters) reads
from here so the rule is defined once. Two levels:

  - ``full`` — all writes allowed. Status = trialing OR active OR past_due.
    past_due gets full access because Stripe is actively retrying the card
    on its own grace ladder (~3 weeks). Cutting the user off mid-retry is
    user-hostile when most past_due states resolve themselves (expired card
    → bank reissues → next retry succeeds).

  - ``read_only`` — reads + exports + GDPR endpoints work; mutations 402.
    Status = canceled / unpaid / incomplete_expired / paused / missing-row.

Read-only mode is meant to keep the *door open*: the user can still see
their data, export it, log back into the Stripe portal to fix payment,
and even delete their account. They just can't create new sessions /
decisions / projects until the sub is healthy again.
"""
from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Subscription

AccessLevel = Literal["full", "read_only"]

# Stripe statuses where the user has full write access. past_due means
# Stripe's smart-retry is mid-cycle — give them benefit of doubt rather
# than gatekeeping during a transient card issue.
FULL_ACCESS_STATUSES: frozenset[str] = frozenset({"trialing", "active", "past_due"})


async def access_level_for_user(
    session: AsyncSession, user_id: str
) -> AccessLevel:
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        # Defensive: a user without a Subscription row should be impossible
        # post-migration 0018. If it happens, fail closed (read-only) so we
        # don't hand out paid access to a row that wasn't bootstrapped.
        return "read_only"
    return "full" if sub.status in FULL_ACCESS_STATUSES else "read_only"
