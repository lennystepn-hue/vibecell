"""Spec-6 Sprint B Phase B2: Stripe glue layer.

Three responsibilities:

1. ``ensure_customer`` — lazy-create a Stripe Customer when a user upgrades,
   record the customer_id in our ``Subscription`` row.

2. ``create_checkout_session`` — kick the user over to Stripe-hosted
   Checkout. Stripe collects card, address, applies VAT (Stripe Tax), and
   returns to ``settings/billing`` with ?success=1.

3. ``handle_webhook`` — verify the signature, dedupe via ``stripe_events``
   table, dispatch the relevant ``customer.subscription.*`` /
   ``invoice.payment_*`` events to the local Subscription mirror.

Failure mode: every endpoint short-circuits with 503 if
``STRIPE_SECRET_KEY`` is unset. We don't want the app to crash at boot
just because we haven't onboarded Stripe yet — but we also don't want
Stripe-dependent features to silently appear to work.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import HangarError
from app.models import Plan, StripeEvent, Subscription, User

logger = logging.getLogger(__name__)


class StripeNotConfiguredError(HangarError):
    """Raised when an endpoint that needs Stripe is hit without
    STRIPE_SECRET_KEY set. Bubbled to a 503 by the route layer."""

    def __init__(self) -> None:
        super().__init__(
            title="Stripe Not Configured",
            status=503,
            type_="/errors/stripe-not-configured",
            detail="Stripe is not configured on this deployment",
        )


class StripeWebhookSignatureError(HangarError):
    """Stripe webhook payload failed signature verification."""

    def __init__(self) -> None:
        super().__init__(
            title="Bad Request",
            status=400,
            type_="/errors/invalid-signature",
            detail="invalid stripe webhook signature",
        )


def _stripe() -> Any:
    """Lazy-import + configure the stripe SDK. Returns the configured module."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise StripeNotConfiguredError()
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

async def ensure_customer(session: AsyncSession, user: User) -> str:
    """Return the Stripe customer_id for ``user``, creating it if needed.

    Lazy creation lets us stay free of Stripe API calls during signup —
    we only touch Stripe the first time the user actually clicks
    "Upgrade to Pro".
    """
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalar_one()
    if sub.stripe_customer_id:
        return sub.stripe_customer_id

    stripe = _stripe()
    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": user.id},
    )
    sub.stripe_customer_id = customer["id"]
    return customer["id"]


# ---------------------------------------------------------------------------
# Checkout
# ---------------------------------------------------------------------------

async def create_checkout_session(
    session: AsyncSession,
    user: User,
    *,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session for upgrading the user to Pro.
    Returns the hosted Checkout URL — caller redirects the browser there.

    Per pricing decision 2026-04-25: 7-day trial, no credit card required
    for trial (``payment_method_collection='if_required'``), Stripe Tax
    enabled, billing address required.
    """
    settings = get_settings()
    if not settings.stripe_pro_price_id:
        raise StripeNotConfiguredError()

    stripe = _stripe()
    customer_id = await ensure_customer(session, user)

    pro_plan = (
        await session.execute(select(Plan).where(Plan.slug == "pro"))
    ).scalar_one()

    checkout = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        automatic_tax={"enabled": True},
        billing_address_collection="required",
        payment_method_collection="if_required",
        subscription_data={
            "trial_period_days": pro_plan.trial_period_days,
        },
    )
    return checkout["url"]


# ---------------------------------------------------------------------------
# Customer Portal
# ---------------------------------------------------------------------------

async def create_portal_session(
    session: AsyncSession,
    user: User,
    *,
    return_url: str,
) -> str:
    """Hand the user off to Stripe's Customer Portal where they can
    update payment method, cancel, view invoices. Stripe-hosted UI."""
    stripe = _stripe()
    customer_id = await ensure_customer(session, user)
    portal = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return portal["url"]


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

# Events we mirror into Subscription. Anything else is acknowledged with 200
# so Stripe stops retrying, but otherwise ignored.
_HANDLED = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",
}


async def handle_webhook(
    session: AsyncSession,
    *,
    raw_body: bytes,
    sig_header: str | None,
) -> dict[str, Any]:
    """Verify signature, dedupe, dispatch. Returns a small ack dict."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise StripeNotConfiguredError()

    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload=raw_body,
            sig_header=sig_header or "",
            secret=settings.stripe_webhook_secret,
        )
    except Exception as e:  # SignatureVerificationError or json error
        logger.warning("stripe webhook signature verify failed: %s", e)
        raise StripeWebhookSignatureError() from e

    event_id: str = event["id"]
    event_type: str = event["type"]

    # Idempotency — if we've seen this event before, ack and skip.
    seen = await session.get(StripeEvent, event_id)
    if seen is not None:
        return {"received": True, "duplicate": True, "event_type": event_type}

    session.add(StripeEvent(id=event_id, type=event_type))

    if event_type in _HANDLED:
        await _apply_event(session, event)

    return {"received": True, "event_type": event_type}


async def _apply_event(session: AsyncSession, event: dict[str, Any]) -> None:
    """Mirror Stripe state changes into our Subscription row."""
    obj = event["data"]["object"]
    customer_id = obj.get("customer")
    if not customer_id:
        return

    sub = (
        await session.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
    ).scalar_one_or_none()
    if sub is None:
        # Event for a customer we don't track — possibly a different
        # environment / leftover from an old deploy. Idempotent ack.
        logger.info(
            "stripe event %s for unknown customer %s — ignoring",
            event["type"], customer_id,
        )
        return

    event_type: str = event["type"]
    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        sub.stripe_subscription_id = obj["id"]
        sub.status = obj["status"]
        sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
        if obj.get("current_period_end"):
            sub.current_period_end = datetime.fromtimestamp(
                obj["current_period_end"], tz=UTC
            )
        if obj.get("trial_end"):
            sub.trial_ends_at = datetime.fromtimestamp(obj["trial_end"], tz=UTC)
    elif event_type == "customer.subscription.deleted":
        sub.status = "canceled"
        sub.cancel_at_period_end = False
        sub.stripe_subscription_id = None
    elif event_type == "invoice.payment_failed":
        sub.status = "past_due"
        # Notify the user. Best-effort — never fail the webhook handler.
        user = await session.get(User, sub.user_id)
        if user is not None:
            from app.core.config import get_settings as _gs
            from app.services.mailer import send_payment_failed_email
            try:
                billing_url = f"{_gs().base_url.rstrip('/')}/settings/billing"
                await send_payment_failed_email(to=user.email, billing_url=billing_url)
            except Exception as e:
                logger.warning("payment_failed email send blew up: %s", e)
