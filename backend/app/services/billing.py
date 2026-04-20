"""Billing service — Stripe subscriptions + plan registry.

Status: STUB — full Stripe integration deferred to Spec 4.1.
All functions are wired and return sensible values; real API calls are gated
behind a `stripe` import that will be added when STRIPE_SECRET_KEY is set.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan Registry
# ---------------------------------------------------------------------------

@dataclass
class Plan:
    id: str
    name: str
    price_usd_cents: int  # monthly, 0 = free
    max_projects: int | None  # None = unlimited
    max_mcp_calls_per_month: int | None
    max_seats: int
    stripe_price_id: str | None = None


_PLANS: dict[str, Plan] = {
    "free": Plan(
        id="free",
        name="Free",
        price_usd_cents=0,
        max_projects=3,
        max_mcp_calls_per_month=500,
        max_seats=1,
        stripe_price_id=None,
    ),
    "pro": Plan(
        id="pro",
        name="Pro",
        price_usd_cents=1200,  # $12/mo
        max_projects=None,
        max_mcp_calls_per_month=10_000,
        max_seats=5,
        stripe_price_id=None,  # set from env: STRIPE_PRO_PRICE_ID
    ),
}


class PlanRegistry:
    """Immutable registry of available subscription plans."""

    @staticmethod
    def get(plan_id: str) -> Plan:
        plan = _PLANS.get(plan_id)
        if plan is None:
            raise KeyError(f"Unknown plan: {plan_id!r}")
        return plan

    @staticmethod
    def all() -> list[Plan]:
        return list(_PLANS.values())

    @staticmethod
    def is_valid(plan_id: str) -> bool:
        return plan_id in _PLANS


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

async def create_checkout_session(
    workspace_id: str,
    user_email: str,
    plan_id: str = "pro",
    success_url: str = "/settings/billing?success=1",
    cancel_url: str = "/pricing",
) -> dict[str, Any]:
    """Create a Stripe Checkout session.

    STUB: Returns 501 payload until STRIPE_SECRET_KEY is configured.
    Full implementation: create stripe.Customer if not exists, call
    stripe.checkout.Session.create(mode='subscription', ...).
    """
    logger.info(
        "billing.create_checkout_session called workspace=%s plan=%s [STUB]",
        workspace_id,
        plan_id,
    )
    # TODO: real impl when stripe library is added
    # from app.core.config import get_settings
    # import stripe
    # stripe.api_key = get_settings().stripe_secret_key
    # session = stripe.checkout.Session.create(...)
    # return {"checkout_url": session.url}
    return {"error": "not_implemented", "detail": "Stripe integration not yet configured"}


# ---------------------------------------------------------------------------
# Customer Portal
# ---------------------------------------------------------------------------

async def create_portal_session(
    workspace_id: str,
    return_url: str = "/settings/billing",
) -> dict[str, Any]:
    """Create a Stripe Billing Portal session for subscription management.

    STUB: Returns not_implemented until Stripe is configured.
    """
    logger.info(
        "billing.create_portal_session called workspace=%s [STUB]", workspace_id
    )
    return {"error": "not_implemented", "detail": "Stripe integration not yet configured"}


# ---------------------------------------------------------------------------
# Webhook handling
# ---------------------------------------------------------------------------

HANDLED_EVENT_TYPES = {
    "checkout.session.completed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
    "invoice.paid",
}


async def handle_webhook(raw_body: bytes, sig_header: str | None) -> dict[str, Any]:
    """Verify Stripe webhook signature + dispatch to event handlers.

    STUB: Signature verification skipped until secret is configured.
    Logs the event type and returns ok=True so Stripe gets a 200.
    Full implementation: use stripe.Webhook.construct_event() to verify,
    then persist to billing_events and update billing_subscriptions.
    """
    # TODO: real signature verification
    # from app.core.config import get_settings
    # import stripe
    # event = stripe.Webhook.construct_event(raw_body, sig_header, get_settings().stripe_webhook_secret)
    import json

    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except Exception:
        logger.warning("billing.handle_webhook: invalid JSON payload")
        return {"ok": False, "error": "invalid_payload"}

    event_type: str = payload.get("type", "unknown")
    event_id: str = payload.get("id", "")
    logger.info(
        "billing.handle_webhook: received event_type=%s id=%s [STUB — not persisted]",
        event_type,
        event_id,
    )

    if event_type not in HANDLED_EVENT_TYPES:
        logger.debug("billing.handle_webhook: unhandled event type %s, ignoring", event_type)

    # TODO: persist to billing_events table + update billing_subscriptions
    return {"ok": True, "event_type": event_type}
