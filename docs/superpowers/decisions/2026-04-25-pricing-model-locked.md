# Pricing model locked: €8.99/month with 7-day trial

**Date:** 2026-04-25
**Decided by:** Lenny (user directive: "mach 8,99 Euro monatlich mit testphase")
**Resolves:** open question #1 from Spec-6 README — "Pricing-Modell: Option 1 vs Option 2?"

## Decision

**Single tier**, single price:

- **Pro plan**: €8.99 / month
- **Trial**: 7 days, no credit card required during trial signup
- After trial ends: requires payment method to keep using AI features
- No "Free Forever" tier — we filter tire-kickers via the trial deadline,
  not via permanent feature gating

This is closer to Option 1 from the original Spec-6 README (single paid tier
with trial) than Option 2 (free + Pro split), but with two refinements:

1. **Price bumped from €6 → €8.99** — better headroom for future Team
   tier, and €8.99 is the de-facto Indie-Devtool sweet spot (Linear €8,
   Cursor Free + Pro €18, Raycast Pro €8). €6 felt like leaving money
   on the table.

2. **Trial does NOT require credit card up front** — original Option 1
   proposed CC-required trial for ~15% trial-to-paid conversion; the
   audit concluded that 60–70% signup drop-off at the CC wall would
   hurt more than the conversion lift gained. With no-CC trial we get
   the funnel-friendly signup of Option 2 and the simpler product
   surface of Option 1.

## What this means in code

Sprint B Phase B0 was supposed to ask for this decision. It's now answered.

`backend/app/db/seed_plans.py` (Phase B1) should seed exactly **one** plan
row — slug `pro`, monthly_price_eur=899 cents, trial_period_days=7. No
"free" plan row.

`Subscription.status` lifecycle:

```
on signup           → trialing  (trial_ends_at = now() + 7d)
trial expires       → past_due  (no payment method on file)
trial expires + pay → active
user cancels        → cancel_at_period_end=true, then canceled
payment fails       → past_due
```

Plan-enforcement layer (Phase B3) gates premium features by:

```python
if sub.status not in ("trialing", "active"):
    raise HTTPException(402, ...)
```

Stripe Tax must still be enabled on the Stripe side (EU VAT). Stripe
Checkout Session config:

```python
subscription_data={"trial_period_days": 7}
automatic_tax={"enabled": True}
billing_address_collection="required"
# payment_method_collection="if_required" — gives free trial without CC
payment_method_collection="if_required"
```

## What this does NOT decide

- **Annual billing** — out of scope for v1, easy to add later (Stripe
  supports it natively; the Plan table just gets a second `stripe_price_id`).
- **Team tier (multi-seat workspaces)** — Spec 7 territory.
- **Discount codes** — post-launch optimisation.
- **Lifetime deal** — not on the table; subscription model only.

## Reconsider if

- Conversion from trial to paid is below 5% after 30 days of real signups
  → tighten the trial (CC required, or shorter)
- Indie-vibecoder users complain €8.99 is too high → split into a Free
  tier (limited projects) + Pro
- A competitor launches at $5 and steals signups → react then, not now
