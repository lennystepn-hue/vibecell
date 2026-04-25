# Sprint B — Billing (Stripe + Plan Enforcement)

> **Goal:** Plan model + Stripe Subscription + Webhook + Customer Portal redirect + Billing UI. Free / Pro tiers with real enforcement.

**Estimated time:** 5 working days (~30 hours)

**Pre-flight check:**
- Sprint A complete and deployed.
- Pricing model locked (Option 1 = €6 + CC trial OR Option 2 = Free + €8 Pro). The implementation differs only in config.
- Stripe account created in **test mode** with EU VAT enabled (Stripe Tax).
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_PRO_MONTHLY` placed in `/etc/hangar/hangar.env`.

---

## Phase B0 — Pricing Decision (15 min)

- [ ] **Step 1: Lock pricing model**

User decides Option 1 or Option 2. Document in `docs/superpowers/decisions/2026-XX-pricing-model.md` and call `vibecell_decision`. The rest of the sprint references which option was picked.

---

## Phase B1 — Plan + Subscription Models

**Why:** Need a place in our DB to mirror Stripe's subscription state. Sole source of truth for "is this user paying?" lives in our DB; Stripe is the upstream that pushes updates.

**Files:**
- Create: `backend/app/models/plan.py`
- Create: `backend/app/models/subscription.py`
- Migration: `backend/alembic/versions/0017_billing.py`
- Seed: `backend/app/db/seed_plans.py`

- [ ] **Step 1: Migration**

```python
# 0017_billing.py
def upgrade() -> None:
    op.create_table(
        "plan",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("slug", sa.String(32), unique=True, nullable=False),  # "free", "pro"
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("stripe_price_id", sa.String(64), nullable=True),  # null for free
        sa.Column("monthly_price_eur", sa.Integer, nullable=False),  # cents
        sa.Column("max_projects", sa.Integer, nullable=True),  # null = unlimited
        sa.Column("ai_enrichment_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("session_retention_days", sa.Integer, nullable=False, server_default=sa.text("365")),
    )

    op.create_table(
        "subscription",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(26), sa.ForeignKey("plan.id"), nullable=False),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),  # "trialing" | "active" | "past_due" | "canceled" | "incomplete"
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_subscription_stripe_customer", "subscription", ["stripe_customer_id"])
```

- [ ] **Step 2: Seed plans**

```python
# backend/app/db/seed_plans.py - run from alembic 0017's data migration step
PLANS = [
    {"slug": "free", "name": "Free", "monthly_price_eur": 0, "max_projects": 1, "ai_enrichment_enabled": False, "session_retention_days": 7},
    {"slug": "pro",  "name": "Pro",  "monthly_price_eur": 800, "max_projects": None, "ai_enrichment_enabled": True, "session_retention_days": 365, "stripe_price_id": "price_..."},
]
```

(Adjust to Option 1 if locked: only one plan `{"slug": "pro", "monthly_price_eur": 600, ...}` and skip the free row.)

- [ ] **Step 3: Auto-create `Subscription` row on user creation**

Modify the user-bootstrap path (Spec 1 Phase 4 — first-login workspace creation). After workspace is created, also insert `Subscription(user=user, plan=free, status="active")` (or `trialing` if Option 1).

- [ ] **Step 4: Test + commit**

```python
async def test_signup_gets_free_plan(client):
    user = await sign_up(...)
    sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    assert sub.scalar_one().plan.slug == "free"
```

```bash
git commit -m "feat(billing): plan + subscription models, free-tier auto-assignment"
```

---

## Phase B2 — Stripe Customer + Checkout + Webhook

**Files:**
- Create: `backend/app/services/stripe_billing.py`
- Create: `backend/app/routes/billing.py` (`/billing/checkout`, `/billing/portal`, `/billing/webhook`)
- Test: `backend/tests/integration/test_stripe_webhook.py` (uses `stripe-mock` Docker container)

- [ ] **Step 1: Service helpers**

```python
# backend/app/services/stripe_billing.py
import stripe

stripe.api_key = settings.STRIPE_SECRET_KEY

async def ensure_customer(session, user) -> str:
    sub = await session.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = sub.scalar_one()
    if sub.stripe_customer_id:
        return sub.stripe_customer_id
    customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.id})
    sub.stripe_customer_id = customer.id
    return customer.id

async def create_checkout_session(customer_id: str, price_id: str, return_url: str) -> str:
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{return_url}?status=ok",
        cancel_url=f"{return_url}?status=cancel",
        automatic_tax={"enabled": True},  # Stripe Tax
        billing_address_collection="required",
        # Option 1 only:
        # subscription_data={"trial_period_days": 7},
    )
    return session.url
```

- [ ] **Step 2: Routes**

```python
@router.post("/billing/checkout")
async def create_checkout(plan_slug: str, current_user: UserDep, session: SessionDep):
    plan = await session.execute(select(Plan).where(Plan.slug == plan_slug))
    plan = plan.scalar_one()
    customer_id = await stripe_billing.ensure_customer(session, current_user)
    await session.commit()
    url = await stripe_billing.create_checkout_session(
        customer_id, plan.stripe_price_id, return_url=f"{settings.FRONTEND_URL}/settings/billing",
    )
    return {"url": url}

@router.post("/billing/portal")
async def open_portal(current_user: UserDep, session: SessionDep):
    """Redirect into Stripe-hosted portal where user can update payment method, cancel, etc."""
    sub = await get_user_subscription(session, current_user.id)
    portal = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.FRONTEND_URL}/settings/billing",
    )
    return {"url": portal.url}

@router.post("/billing/webhook")
async def stripe_webhook(request: Request, session: SessionDep):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    await stripe_billing.handle_event(session, event)
    await session.commit()
    return {"ok": True}
```

- [ ] **Step 3: Webhook event handler**

Handle these event types:

| Stripe event | Action |
|---|---|
| `customer.subscription.created` | Set `Subscription.plan` = pro, `status` = `trialing` or `active`, `trial_ends_at`, `current_period_end` |
| `customer.subscription.updated` | Update `status`, `current_period_end`, `cancel_at_period_end` |
| `customer.subscription.deleted` | Demote to free plan, clear stripe_subscription_id |
| `invoice.payment_failed` | Set `status` = `past_due`, send email |
| `invoice.payment_succeeded` | (Idempotent — already covered by subscription.updated) |

```python
async def handle_event(session, event):
    obj = event["data"]["object"]
    customer_id = obj.get("customer")
    if not customer_id:
        return
    sub = await session.execute(select(Subscription).where(Subscription.stripe_customer_id == customer_id))
    sub = sub.scalar_one_or_none()
    if not sub:
        return  # event for a customer we don't track

    if event["type"] in ("customer.subscription.created", "customer.subscription.updated"):
        sub.stripe_subscription_id = obj["id"]
        sub.status = obj["status"]
        sub.current_period_end = datetime.fromtimestamp(obj["current_period_end"], tz=timezone.utc)
        if obj.get("trial_end"):
            sub.trial_ends_at = datetime.fromtimestamp(obj["trial_end"], tz=timezone.utc)
        sub.cancel_at_period_end = obj.get("cancel_at_period_end", False)
        # Find plan by stripe price
        price_id = obj["items"]["data"][0]["price"]["id"]
        plan = await session.execute(select(Plan).where(Plan.stripe_price_id == price_id))
        sub.plan = plan.scalar_one()
    elif event["type"] == "customer.subscription.deleted":
        free = await session.execute(select(Plan).where(Plan.slug == "free"))
        sub.plan = free.scalar_one()
        sub.status = "canceled"
        sub.stripe_subscription_id = None
    elif event["type"] == "invoice.payment_failed":
        sub.status = "past_due"
        await send_payment_failed_email(sub.user)
```

- [ ] **Step 4: Idempotency**

Stripe retries webhooks. Add a `stripe_event` table tracking processed event IDs:

```python
# in 0017 migration
op.create_table(
    "stripe_event",
    sa.Column("id", sa.String(64), primary_key=True),  # Stripe's evt_xxx id
    sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
)
```

In `handle_event`: check if `event["id"]` exists; if so, return early.

- [ ] **Step 5: Test against `stripe-mock`**

`docker run -p 12111:12111 stripe/stripe-mock`. Point `stripe.api_base = "http://localhost:12111"` in test fixture. Forge a webhook payload + signature using `stripe.Webhook.generate_test_header_string`. Assert the DB rows update correctly.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(billing): Stripe checkout + customer portal + idempotent webhook"
```

---

## Phase B3 — Plan Enforcement Layer

**Why:** Database state is meaningless without an enforcement point. Free users hitting "create 2nd project" must get a 402 with an upgrade CTA.

**Files:**
- Create: `backend/app/dependencies/plan_gate.py`
- Modify: `backend/app/routes/projects.py` (gate `POST /projects`)
- Modify: `backend/app/services/enrichment.py` (gate AI calls)
- Modify: cron job `backend/app/jobs/cleanup.py` (purge sessions older than `plan.session_retention_days`)

- [ ] **Step 1: Dependency**

```python
# backend/app/dependencies/plan_gate.py
async def require_under_project_limit(current_user: UserDep, session: SessionDep):
    sub = await get_user_subscription(session, current_user.id)
    plan = sub.plan
    if plan.max_projects is None:
        return  # unlimited
    count = await session.scalar(select(func.count(Project.id)).where(Project.workspace_id == current_user.active_workspace_id))
    if count >= plan.max_projects:
        raise HTTPException(402, detail={
            "error": "project_limit_reached",
            "limit": plan.max_projects,
            "upgrade_url": "/settings/billing",
        })

async def require_ai_enrichment_enabled(current_user: UserDep, session: SessionDep):
    sub = await get_user_subscription(session, current_user.id)
    if not sub.plan.ai_enrichment_enabled:
        raise HTTPException(402, detail={"error": "feature_locked", "feature": "ai_enrichment"})
```

- [ ] **Step 2: Apply gate**

```python
@router.post("/projects", dependencies=[Depends(require_under_project_limit)])
async def create_project(...): ...

@router.post("/projects/{slug}/enrich", dependencies=[Depends(require_ai_enrichment_enabled)])
async def enrich_project(...): ...
```

- [ ] **Step 3: Session-retention cleanup cron**

```python
# backend/app/jobs/cleanup.py
async def purge_old_sessions(session):
    # For each user, delete sessions older than their plan.session_retention_days
    # Run daily at 3am
    cutoff = datetime.now(timezone.utc) - timedelta(days=...)
    ...
```

Wire into APScheduler.

- [ ] **Step 4: Test the 402 path**

```python
async def test_free_user_cannot_create_second_project(client, free_authed_user):
    await client.post("/projects", json={"name": "first", "slug": "first"})
    resp = await client.post("/projects", json={"name": "second", "slug": "second"})
    assert resp.status_code == 402
    assert resp.json()["detail"]["error"] == "project_limit_reached"
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(billing): plan enforcement on project + enrichment endpoints"
```

---

## Phase B4 — Billing Page UI + Trial Banner

**Files:**
- Create: `frontend/src/pages/SettingsBilling.vue`
- Create: `frontend/src/components/TrialBanner.vue`
- Modify: `frontend/src/layouts/AppLayout.vue` (mount TrialBanner above main content)

- [ ] **Step 1: `/settings/billing` page**

Layout:
- Card "Current plan": shows plan name + price + status. If `status == 'trialing'`, shows "Trial ends in X days". If `past_due`, shows red banner "Payment failed — update card".
- Button "Upgrade to Pro" (free users) → POST `/billing/checkout` → redirect to Stripe Checkout.
- Button "Manage subscription" (paying users) → POST `/billing/portal` → redirect to Stripe Customer Portal.
- Section "Invoices": iframe-or-link to Stripe portal (don't reimplement invoice rendering).

- [ ] **Step 2: TrialBanner component**

```vue
<!-- shows on every page when user is in trial OR past_due -->
<template>
  <div v-if="show" class="banner banner--warn">
    <span>{{ message }}</span>
    <RouterLink to="/settings/billing">Manage</RouterLink>
  </div>
</template>
```

`show` = `subscription.status === 'trialing' || 'past_due'`.

- [ ] **Step 3: Composable `useSubscription()`**

Pinia store fetches `/me/subscription` on app boot, refreshes on focus.

- [ ] **Step 4: Vitest + Playwright**

```typescript
test("free user sees upgrade CTA", async ({ page }) => {
  await page.goto("/settings/billing");
  await expect(page.getByRole("button", { name: /upgrade to pro/i })).toBeVisible();
});
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(billing): /settings/billing page + global trial banner"
```

---

## Phase B5 — Email Templates (Trial-End / Payment-Failed / Welcome)

**Files:**
- `backend/app/email_templates/trial_ending.html`
- `backend/app/email_templates/payment_failed.html`
- `backend/app/email_templates/subscription_canceled.html`
- Modify: `backend/app/services/email.py` (add helpers)

- [ ] **Step 1: Templates**

Plain HTML, single CTA button. Brand-aligned with Vibecell colors (violet/mint/pink). Use existing magic-link template as the base.

- [ ] **Step 2: Trial-ending cron**

Daily job: find subscriptions where `trial_ends_at < now() + 2 days` AND no email sent yet → send `trial_ending` template. Track sent state in `subscription.last_trial_email_at`.

- [ ] **Step 3: Test + commit**

```bash
git commit -m "feat(billing): trial-ending + payment-failed transactional emails"
```

---

## Sprint B Done-Definition

- [ ] All 6 phases committed and deployed
- [ ] Stripe webhook is live (configure in Stripe dashboard pointing to `https://vibecell.dev/billing/webhook`)
- [ ] One full happy-path tested end-to-end: signup → upgrade → Stripe Checkout → webhook → DB shows `status=active` → billing page reflects it
- [ ] One refund-path tested: cancel via portal → webhook → DB shows `cancel_at_period_end=true` → after period end, demoted to free
- [ ] CI green on `main`
- [ ] Tag `v0.6.B-billing && git push --tags`
