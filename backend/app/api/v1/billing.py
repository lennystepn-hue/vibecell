"""Billing API — Stripe checkout + webhook + customer portal.

Spec 4 — Launch-Enabler. All endpoints are scaffolded; full Stripe integration
is deferred to Spec 4.1. Checkout + portal return 501; webhook returns 200
(required by Stripe — must never 500).
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services import billing as billing_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


class CheckoutRequest:
    def __init__(self, plan_id: str = "pro") -> None:
        self.plan_id = plan_id


from pydantic import BaseModel


class CheckoutBody(BaseModel):
    plan_id: str = "pro"


class PortalBody(BaseModel):
    return_url: str = "/settings/billing"


@router.post("/checkout")
async def create_checkout(
    body: CheckoutBody,
    ctx: AuthDep,
    db: DbDep,
) -> JSONResponse:
    """Create a Stripe Checkout session for upgrading to Pro.

    Returns 501 until STRIPE_SECRET_KEY is configured.
    """
    result = await billing_svc.create_checkout_session(
        workspace_id=ctx.active_workspace_id,
        user_email=ctx.user.email,
        plan_id=body.plan_id,
    )
    if result.get("error") == "not_implemented":
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=result,
        )
    return JSONResponse(content=result)


@router.post("/portal")
async def create_portal(
    body: PortalBody,
    ctx: AuthDep,
    db: DbDep,
) -> JSONResponse:
    """Create a Stripe Billing Portal session for subscription management.

    Returns 501 until Stripe is configured.
    """
    result = await billing_svc.create_portal_session(
        workspace_id=ctx.active_workspace_id,
        return_url=body.return_url,
    )
    if result.get("error") == "not_implemented":
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content=result,
        )
    return JSONResponse(content=result)


@router.post("/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Receive and process Stripe webhook events.

    MUST return 200 quickly — Stripe will retry on non-200.
    Signature verification is stubbed; event is logged but not persisted.
    """
    raw_body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    result = await billing_svc.handle_webhook(raw_body=raw_body, sig_header=sig_header)

    if not result.get("ok"):
        logger.warning("billing.webhook: rejected payload")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=result,
        )

    return JSONResponse(content={"received": True, "event_type": result.get("event_type")})


@router.get("/plans")
async def list_plans() -> list[dict[str, Any]]:
    """List available subscription plans (public endpoint, no auth required)."""
    plans = billing_svc.PlanRegistry.all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "price_usd_cents": p.price_usd_cents,
            "max_projects": p.max_projects,
            "max_mcp_calls_per_month": p.max_mcp_calls_per_month,
            "max_seats": p.max_seats,
        }
        for p in plans
    ]
