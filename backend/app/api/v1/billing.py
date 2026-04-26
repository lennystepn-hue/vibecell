"""Billing API — Stripe Checkout + Portal + Webhook (Spec-6 Sprint B2).

Endpoints:
  POST /api/v1/billing/checkout   — auth, returns {url} for Stripe Checkout
  POST /api/v1/billing/portal     — auth, returns {url} for Stripe Customer Portal
  POST /api/v1/billing/webhook    — public, Stripe POSTs here
  GET  /api/v1/billing/plans      — public, lists plans from DB

Stripe-not-configured returns 503 across all of them; the SDK is only
loaded if STRIPE_SECRET_KEY is set in the env.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Plan
from app.services import stripe_billing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


class CheckoutBody(BaseModel):
    plan_id: str = "pro"


class CheckoutResponse(BaseModel):
    url: str


class PortalBody(BaseModel):
    return_url: str = "/settings/billing"


class PortalResponse(BaseModel):
    url: str


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutBody,
    auth: AuthDep,
    db: DbDep,
) -> CheckoutResponse:
    """Create a Stripe Checkout Session and return the hosted URL.
    Frontend redirects window.location to it.

    ``body.plan_id`` selects ``pro`` (monthly, default) or ``pro_annual``.
    Raises 503 if Stripe isn't configured on this deployment.
    """
    settings = get_settings()
    base = settings.base_url.rstrip("/")
    plan_slug = body.plan_id if body.plan_id in ("pro", "pro_annual") else "pro"
    url = await stripe_billing.create_checkout_session(
        db,
        auth.user,
        success_url=f"{base}/settings/billing?status=ok",
        cancel_url=f"{base}/settings/billing?status=cancel",
        plan_slug=plan_slug,
    )
    await db.commit()
    return CheckoutResponse(url=url)


class LaunchStatusResponse(BaseModel):
    active: bool
    remaining: int
    max: int


@router.get("/launch-status", response_model=LaunchStatusResponse)
async def launch_status() -> LaunchStatusResponse:
    """Public endpoint — no auth. Used by the Pricing page to render the
    launch ribbon + spots-left counter."""
    s = await stripe_billing.get_launch_coupon_status()
    return LaunchStatusResponse(active=s["active"], remaining=s["remaining"], max=s["max"])


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalBody,
    auth: AuthDep,
    db: DbDep,
) -> PortalResponse:
    """Hand the user off to Stripe-hosted Customer Portal.
    Lets them update payment method, cancel, view invoices."""
    settings = get_settings()
    base = settings.base_url.rstrip("/")
    return_url = body.return_url
    if not return_url.startswith("http"):
        return_url = f"{base}{return_url if return_url.startswith('/') else '/' + return_url}"
    url = await stripe_billing.create_portal_session(
        db,
        auth.user,
        return_url=return_url,
    )
    await db.commit()
    return PortalResponse(url=url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: DbDep,
) -> dict[str, Any]:
    """Stripe POSTs subscription / invoice events here. Endpoint MUST
    return 2xx fast — Stripe retries with exponential backoff on errors.

    Signature is verified via stripe.Webhook.construct_event using the
    STRIPE_WEBHOOK_SECRET env var. Idempotency dedupe via stripe_events
    table.
    """
    raw = await request.body()
    sig = request.headers.get("stripe-signature")
    result = await stripe_billing.handle_webhook(db, raw_body=raw, sig_header=sig)
    await db.commit()
    return result


@router.get("/plans")
async def list_plans(db: DbDep) -> list[dict[str, Any]]:
    """Public endpoint — no auth required. Used by /pricing page."""
    plans = (await db.execute(select(Plan))).scalars().all()
    return [
        {
            "slug": p.slug,
            "name": p.name,
            "monthly_price_eur_cents": p.monthly_price_eur_cents,
            "max_projects": p.max_projects,
            "ai_enrichment_enabled": p.ai_enrichment_enabled,
            "session_retention_days": p.session_retention_days,
            "trial_period_days": p.trial_period_days,
        }
        for p in plans
    ]
