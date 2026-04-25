"""Spec-6 Sprint B Phase B2: billing endpoint smoke tests.

These tests run WITHOUT a real Stripe configured (HANGAR_STRIPE_SECRET_KEY
empty in CI), so the Stripe-dependent endpoints return 503. The /plans
endpoint is testable end-to-end.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_list_plans_returns_seeded_pro(session: AsyncSession) -> None:
    """The Pro plan is seeded by alembic 0017 and should be listable."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            resp = await client.get("/api/v1/billing/plans")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) == 1
    pro = plans[0]
    assert pro["slug"] == "pro"
    assert pro["monthly_price_eur_cents"] == 899
    assert pro["trial_period_days"] == 7
    assert pro["max_projects"] is None


async def test_checkout_503_when_stripe_unconfigured(session: AsyncSession) -> None:
    """Without STRIPE_SECRET_KEY in the environment, /checkout must 503,
    not 500. The frontend renders this as 'Stripe not configured'."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            await sign_in(client, session, "checkout-503@example.com")
            resp = await client.post(
                "/api/v1/billing/checkout",
                json={"plan_id": "pro"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 503


async def test_portal_503_when_stripe_unconfigured(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            await sign_in(client, session, "portal-503@example.com")
            resp = await client.post(
                "/api/v1/billing/portal",
                json={"return_url": "/settings/billing"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 503


async def test_webhook_503_when_stripe_unconfigured(session: AsyncSession) -> None:
    """Stripe webhook with no STRIPE_WEBHOOK_SECRET configured. Must 503,
    not 500 — Stripe will retry less aggressively on documented 5xx."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as client:
            resp = await client.post(
                "/api/v1/billing/webhook",
                content=b'{"type":"customer.subscription.created"}',
                headers={"stripe-signature": "fake"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 503
