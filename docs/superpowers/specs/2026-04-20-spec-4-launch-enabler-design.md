# Spec 4 — Launch-Enabler Design

**Date**: 2026-04-20  
**Status**: Scaffolded (MVP stubs committed)  
**Owner**: vibecell.dev core

---

## Overview

Spec 4 makes vibecell.dev launchable to real users. Three pillars: accept payments via Stripe, support passkey (WebAuthn) login as an alternative to magic links, and provide public-facing pages for unauthenticated visitors. Without these, vibecell cannot be publicly marketed, monetized, or trusted by privacy-conscious users.

---

## 1. Billing — Stripe Subscriptions

### Goals

Enable Free and Pro subscription tiers. Collect payment, enforce usage limits per plan, surface billing management to users.

### Plan Registry

Two initial plans:

| Plan  | Price  | Projects | MCP calls/mo | Seats |
|-------|--------|----------|--------------|-------|
| Free  | $0     | 3        | 500          | 1     |
| Pro   | $12/mo | Unlimited| 10,000       | 5     |

Plan metadata lives in `PlanRegistry` (Python dict keyed by `plan_id`). The Workspace model already has a `plan` field (default `"free"`).

### Database

**`billing_subscriptions`** — one row per workspace, tracks Stripe subscription state:
- `id` (ULID PK), `workspace_id` (FK → workspaces, unique), `stripe_customer_id`, `stripe_subscription_id`, `plan_id`, `status` (`trialing | active | past_due | canceled`), `current_period_end`, `cancel_at_period_end` (bool), `created_at`, `updated_at`

**`billing_events`** — append-only log of Stripe webhook events received:
- `id` (ULID PK), `workspace_id` (FK nullable — resolved from customer), `stripe_event_id` (unique), `event_type`, `payload` (JSONB), `processed_at`

### Flows

**Checkout**: `POST /api/v1/billing/checkout` → calls Stripe Checkout Sessions API with `mode=subscription`, `success_url=/settings/billing?success=1`, `cancel_url=/pricing`. Returns `{checkout_url}`. Requires auth; workspace resolved from session.

**Webhook**: `POST /api/v1/billing/webhook` → Stripe POSTs signed events here. Verify with `stripe.Webhook.construct_event(payload, sig_header, secret)`. Handle: `checkout.session.completed` (create/update subscription row), `customer.subscription.updated` (sync status), `customer.subscription.deleted` (set canceled), `invoice.payment_failed` (set past_due). Persist to `billing_events`. Endpoint must return 200 quickly.

**Customer Portal**: `POST /api/v1/billing/portal` → returns Stripe Billing Portal session URL. User is redirected to manage their subscription (cancel, update card, view invoices).

### Usage Enforcement

Middleware or dependency check: `require_plan(min_plan="pro")` decorator. Future work. For now the plan field on Workspace is the source of truth.

### Environment Variables Needed

`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRO_PRICE_ID`

---

## 2. Passkeys — WebAuthn

### Goals

Let users register and authenticate with a passkey (Touch ID, Face ID, hardware key) instead of magic links. Passkeys are phishing-resistant and improve trust signals for launch.

### Library

`webauthn` Python package (py_webauthn). Uses CBOR/COSE internally, handles challenge generation, credential parsing, and signature verification.

### Credential Storage

`User.passkey_credentials` is already a `JSONB` column. Store a list of credential objects:

```json
[
  {
    "id": "<base64url credential id>",
    "public_key": "<base64url COSE public key>",
    "sign_count": 42,
    "transports": ["internal"],
    "created_at": "2026-04-20T00:00:00Z"
  }
]
```

Multiple credentials per user are supported (e.g. multiple devices).

### Registration Flow

1. `POST /api/v1/passkey/register/begin` (requires auth) — generates registration options (challenge, rpId, user). Challenge stored in session (Redis-backed). Returns JSON options consumed by `navigator.credentials.create()` on the frontend.
2. `POST /api/v1/passkey/register/finish` (requires auth) — receives `PublicKeyCredential` response. Verify with `webauthn.verify_registration_response()`. On success, append new credential to `user.passkey_credentials`.

### Authentication Flow

1. `POST /api/v1/passkey/auth/begin` — accepts `{email}` (or anonymous if user already has a session). Looks up user by email, generates assertion options with their credential IDs as `allowCredentials`. Challenge stored in session.
2. `POST /api/v1/passkey/auth/finish` — receives assertion response. Verify with `webauthn.verify_authentication_response()`. On success, set session cookie (same path as magic link auth).

### Security Notes

- RP ID must match the domain: `vibecell.dev` in prod, `localhost` in dev.
- Challenges are single-use, expire after 5 minutes (TTL in Redis).
- Sign count must be monotonically increasing (detect cloned authenticators).

### Environment Variables Needed

`WEBAUTHN_RP_ID` (e.g. `vibecell.dev`), `WEBAUTHN_RP_NAME` (e.g. `Vibecell`), `WEBAUTHN_ORIGIN` (e.g. `https://vibecell.dev`)

---

## 3. Public Pages

### Problem

Currently `/` redirects to `/login` for unauthenticated users. There is no landing page, pricing page, or legal content. This means vibecell.dev cannot be shared, marketed, or submitted to Product Hunt.

### Route Split

- `/` — `AnonLanding.vue` if unauthed; `IndexRedirect.vue` behaviour (→ `/p`) if authed.
- `/pricing` — `Pricing.vue` (public, no auth required).
- `/legal` — `Legal.vue` (public, no auth required). Renders tab-based view of Privacy Policy and Terms of Service markdown.
- `/docs` — future, placeholder redirect to external docs or a static page.

The router guard already supports `meta: { anonymous: true }` — add this to the new public routes.

### AnonLanding Content

Hero: "Vibecell — Remember every project you ship."  
Subheadline: The project context layer for solo builders and indie hackers.  
Value props:
- **Context, not chaos** — Every project keeps its own context, focus, and next step. Your AI assistant always knows where you left off.
- **MCP-native** — Connect Claude (or any MCP client) directly. No copy-paste, no context windows blown.
- **One workspace, many projects** — Track decisions, sessions, and ships across your whole portfolio.

CTA: "Sign in free →" links to `/login`.

### Pricing Page Content

Show Free vs Pro cards. Highlight what's included at each tier. Link to checkout (stub — CTA shows modal "coming soon" until billing is live).

### Legal Page Content

Tab between Privacy Policy and Terms of Service. Both rendered from inline markdown strings (not external files) for simplicity. Cookie banner: a fixed bottom bar that sets `localStorage.cookie_consent = 'accepted'` and disappears.

---

## 4. GDPR Compliance

**Data Export**: `GET /api/v1/me/export` — returns a JSON blob of all user data (projects, ships, decisions, sessions, notes). Status: stub returning 501 until implemented.

**Right to Delete**: `DELETE /api/v1/me` — already planned. Cascades handled at DB level via `ON DELETE CASCADE`.

**Cookie Banner**: frontend only. Sets consent flag in localStorage. No tracking cookies exist yet beyond the session cookie (necessary, no consent needed).

---

## Implementation Phases

| Phase | Work | Est. |
|-------|------|------|
| 4.1   | Billing tables + Stripe checkout + webhook (real impl) | 3d |
| 4.2   | Passkey registration + authentication (real impl) | 2d |
| 4.3   | AnonLanding + Pricing + Legal pages (polished) | 1d |
| 4.4   | GDPR export endpoint + cookie banner | 1d |
| 4.5   | Usage enforcement middleware | 1d |

---

## Open Questions

- Do we offer annual billing? (30% discount is standard.)
- Trial period for Pro? (14 days free trial recommended for initial launch.)
- Which passkey libraries to use on the frontend? (`@simplewebauthn/browser` is the standard choice.)
- Self-service workspace deletion or contact-us flow?
