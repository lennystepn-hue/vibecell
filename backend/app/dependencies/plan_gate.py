"""Spec-6 Sprint B Phase B3: plan-enforcement dependency layer.

Endpoints that gate features behind a paid plan declare the dependency
once; if the user's current Subscription doesn't grant access, a 402
Payment Required is raised before the handler body runs.

Design choices:
- Returns silently when the user has access (so handlers stay clean).
- Treats `trialing` as `active` for feature access — that's the whole
  point of a trial. Trials become `past_due` when payment fails or the
  trial ends without a payment method.
- The 402 response body includes ``upgrade_url`` so the frontend can
  redirect or show an inline upgrade card.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Plan, Project, Subscription

_PAID_STATUSES = {"trialing", "active"}


async def _get_user_plan(
    session: AsyncSession, user_id: str
) -> tuple[Subscription, Plan]:
    """Load the user's Subscription + the Plan it points at. Raises 500 if
    a User row exists without a Subscription — that should be impossible
    after the B1 bootstrap, but we catch it loudly rather than silently
    granting access."""
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(
            status_code=500,
            detail="user has no subscription row — login bootstrap broken?",
        )
    plan = await session.get(Plan, sub.plan_id)
    if plan is None:
        raise HTTPException(
            status_code=500,
            detail="subscription points at non-existent plan",
        )
    return sub, plan


async def require_under_project_limit(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Refuse the request with 402 if the user's plan caps the project
    count and they're already at it."""
    sub, plan = await _get_user_plan(db, auth.user.id)
    if sub.status not in _PAID_STATUSES:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "subscription_inactive",
                "status": sub.status,
                "upgrade_url": "/settings/billing",
            },
        )
    if plan.max_projects is None:
        return  # unlimited

    count = await db.scalar(
        select(func.count(Project.id)).where(
            Project.workspace_id == auth.active_workspace_id
        )
    )
    if (count or 0) >= plan.max_projects:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "project_limit_reached",
                "limit": plan.max_projects,
                "upgrade_url": "/settings/billing",
            },
        )


async def require_ai_enrichment_enabled(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Refuse the request with 402 if the user's plan disables AI
    enrichment (or their subscription is past_due / canceled)."""
    sub, plan = await _get_user_plan(db, auth.user.id)
    if sub.status not in _PAID_STATUSES:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "subscription_inactive",
                "status": sub.status,
                "upgrade_url": "/settings/billing",
            },
        )
    if not plan.ai_enrichment_enabled:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "feature_locked",
                "feature": "ai_enrichment",
                "upgrade_url": "/settings/billing",
            },
        )
