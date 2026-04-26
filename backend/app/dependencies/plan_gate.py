"""Spec-6 — FastAPI dependencies that gate REST routes by plan + subscription.

Three composable dependencies:

  - ``require_active_subscription`` — bare gate. Pass it as the dependency
    on any endpoint that should refuse to mutate state for read-only
    users. 402 with detail.upgrade_url so the frontend can render an
    inline upgrade card.

  - ``require_under_project_limit`` — for POST /projects specifically. Adds
    the per-plan project-count cap on top of the active-sub check.

  - ``require_ai_enrichment_enabled`` — for endpoints that call Anthropic
    on the platform's dime. Refuses if the plan disables AI features.

All three read from ``app.services.access_level`` so the rule of "what
counts as full access" lives in exactly one place. Sprint-A endpoints
that MUST stay reachable in read-only mode (data export, account
delete, billing portal/checkout, auth, /me/subscription) intentionally
do NOT use these gates.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Plan, Project, Subscription
from app.services.access_level import access_level_for_user


def _detail_inactive(reason: str = "subscription_inactive") -> dict[str, str]:
    return {
        "error": reason,
        "upgrade_url": "/settings/billing",
        "message": (
            "Subscription expired — Vibecell is read-only. "
            "Renew to keep mutating projects, sessions, decisions, and ships."
        ),
    }


async def require_active_subscription(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Refuse with 402 if the user is in read-only mode."""
    level = await access_level_for_user(db, auth.user.id)
    if level != "full":
        raise HTTPException(status_code=402, detail=_detail_inactive())


async def require_under_project_limit(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Refuse if read-only OR project-count >= plan.max_projects."""
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == auth.user.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        # Same defensive treatment as access_level_for_user — no row =
        # read-only, no project create.
        raise HTTPException(status_code=402, detail=_detail_inactive())

    level = await access_level_for_user(db, auth.user.id)
    if level != "full":
        raise HTTPException(status_code=402, detail=_detail_inactive())

    plan = await db.get(Plan, sub.plan_id)
    if plan is None or plan.max_projects is None:
        return  # unlimited tier

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
    """Refuse if read-only OR plan.ai_enrichment_enabled is False."""
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == auth.user.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=402, detail=_detail_inactive())

    level = await access_level_for_user(db, auth.user.id)
    if level != "full":
        raise HTTPException(status_code=402, detail=_detail_inactive())

    plan = await db.get(Plan, sub.plan_id)
    if plan is None or not plan.ai_enrichment_enabled:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "feature_locked",
                "feature": "ai_enrichment",
                "upgrade_url": "/settings/billing",
            },
        )
