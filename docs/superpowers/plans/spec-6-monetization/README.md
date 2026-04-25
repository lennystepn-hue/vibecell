# Spec 6 — Monetization & Public-Launch Readiness

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement the sprint files below. Each sprint is independently shippable; sprints are sequenced because later ones assume features from earlier ones.

**Goal:** Take Vibecell from "free beta with no payment surface" to "publicly launched, billable SaaS with the legal + operational hygiene a paying user expects".

**Spec:** This document. (No formal spec — derived from the post-Spec-3.5 hardening discussion 2026-04-25.)

**Architecture:** Three sequential sprints, each ~3–7 days of focused work. Sprint A makes the product safe to charge for; Sprint B introduces the billing surface; Sprint C wraps a public-launch story around it. Stripe is the payment provider. Free tier (1 project, no AI enrichment, 7-day session retention) opens the funnel; €8/month "Pro" unlocks unlimited use. EU VAT handled by Stripe Tax.

**Tech Stack additions on top of Spec 1/3.5:** Stripe Python SDK + webhook handler, Sentry-Python + Sentry-Vue, Resend templates (already in stack — extended with new flows), Vue billing page, three new Postgres tables (`plan`, `subscription`, `email_verification_token`), one new Alembic migration per sprint.

---

## Sprint Order

| # | Sprint | File | Output | Est. |
|---|---|---|---|---|
| A | Hardening — make it safe to charge for | [sprint-A-hardening.md](sprint-A-hardening.md) | email verification, password reset, account delete + GDPR export, Postgres backup cron, Sentry, real rate-limits | 5 d |
| B | Billing — Stripe + plan enforcement | [sprint-B-billing.md](sprint-B-billing.md) | plan/subscription model, Stripe Customer + Subscription + Webhook, Stripe Tax, Customer Portal redirect, billing page UI, trial countdown | 5 d |
| C | Public Launch — pricing, legals, onboarding | [sprint-C-launch.md](sprint-C-launch.md) | pricing page, Impressum + ToS + Privacy, first-project onboarding wizard, public status page, launch checklist | 3 d |

**Total:** ~13 working days. Stripe webhook + EU VAT eat half of Sprint B; the rest is mostly ergonomic glue.

---

## Pricing Decision (still open — flag in spec)

**Option 1 — User's original proposal:** €6/month flat, 7-day trial requiring credit card up front.
- Pro: filters tire-kickers, ~15% trial→paid conversion
- Con: ~60–70% signup drop-off at the CC wall, brand-unfriendly for a v1 dev tool with no recognition

**Option 2 — Recommended (Lenny + Claude consensus pending):** Free-forever tier (1 project, no AI enrichment, 7-day retention) → upgrade to Pro at €8/month for unlimited.
- Pro: low signup friction, "aha"-moment on day 1, Twitter-shareable
- Con: lower trial conversion, more support load from free users

**The plan is written so either model works** — Sprint B builds the plan/subscription primitives either way. The difference is the enforcement-layer config (`MAX_PROJECTS_FREE`, `AI_ENRICHMENT_FREE_ENABLED`) and the Pricing-Page copy.

**Decision deadline:** end of Sprint A. Sprint B's first task asks the user to lock the model.

---

## Working rules (all sprints)

- **TDD where it makes sense.** Stripe webhook handler MUST have integration tests against `stripe-mock`. Backup-cron only needs a smoke test. Onboarding-wizard is mostly UI — Vitest + Playwright cover it.
- **One sprint = one tagged release.** End each sprint with a `v0.6.A`, `v0.6.B`, `v0.6.C` git tag and a deploy. Easier to roll back.
- **Real Stripe-test-mode end-to-end.** Don't trust mocks-only — at least one full happy-path test ("create customer → checkout → webhook → plan upgraded") runs against Stripe test mode in CI.
- **No skipped DSGVO.** Account-delete + data-export are not nice-to-have. They block German users legally.
- **Migrations are forward-only.** Each sprint adds at most one Alembic migration. No `alembic downgrade` in production.
- **Email-flows ship behind feature-flag** until the templates are reviewed.
- **Windows note.** Same as previous specs — bash everywhere, forward slashes, no PowerShell-specific commands.

---

## Out of scope (explicitly)

- Team-tier pricing (multi-seat workspaces) — Spec 7 territory
- Annual billing / discount codes — post-launch optimization
- Mobile-friendly responsive design pass — separate UX track
- SOC2 / ISO27001 audit prep — irrelevant until enterprise-tier exists
- Affiliate program / referrals — post-launch
- Dunning emails beyond Stripe defaults — start with Stripe's built-in retry, optimize later

---

## Known Issues this plan does NOT touch

These remain as project `known_issues` in Vibecell and are tracked separately:

- `test_register_rate_limit` skipped — handled in Sprint A, Phase A6
- `ProjectDetail.spec` skipped — pure test debt, doesn't block launch
- ~20 legacy services with `mypy ignore_errors` — also pure debt
- Spec 7 (whatever it ends up being) — separate plan

---

## Sprint dependencies

```
Sprint A (no deps) ──► Sprint B (needs email-verification + Sentry) ──► Sprint C (needs billing live)
                                                                  │
                                                  Sprint C can start in parallel
                                                  with B once B's plan model lands.
```
