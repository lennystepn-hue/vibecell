# Email verification is already implicit via magic-link

**Date:** 2026-04-25
**Context:** Spec 6 Sprint A planning, Phase A1 audit step.

## Finding

Vibecell uses magic-link as the **only** authentication method. Users sign in via:

1. POST `/api/v1/auth/magic-link` with email
2. Receive a one-time link via Resend
3. GET `/api/v1/auth/verify?token=...` from that link
4. Server creates user (first login) or session (returning user)

The flow is implemented in `app/services/login.py::verify_magic_link`. Inspection of `backend/app/services/login.py` confirms:

- The **only** code path that creates a `User` row is `verify_magic_link` (verified via `grep -r "User(" backend/app/`).
- That code path only runs after the user has clicked a token sent to their email.
- No `email_verified_at` column exists on the User model today.

## Decision

**Email verification is already happening.** Every Vibecell account holder has, by definition, demonstrated control of the email on file. The right move is **not** to bolt on a second verification flow — it's to **record** the fact that magic-link already verified the email.

## Implications for the plan

The original Sprint A Phase A1 (in `docs/superpowers/plans/spec-6-monetization/sprint-A-hardening.md`) proposed:

- A new `email_verification_token` table
- A new `/auth/verify-email` endpoint
- A new resend endpoint
- A frontend `/auth/verify-email/:token` page
- Email template + integration test

All of that is **redundant**. Phase A1 reduces to:

- Add `email_verified_at: datetime | None` column to `User` model
- Set it inside `verify_magic_link` on the first successful verify (idempotent)
- One migration, one ~3-line change to `login.py`, one test

**Estimated time savings:** ~4 hours of Sprint A.

The original A1 design is preserved as Phase A2 (email-**change** flow) which **does** need the new token table — when a user wants to change their email, the **new** email must be verified independently of magic-link login. That use-case justifies the token infrastructure that A1 was going to build.

## What we lose

Nothing. The shipped product is functionally identical: every account is email-verified.

## What we gain

- A single source of truth (`User.email_verified_at`) that downstream code (Stripe customer creation, future SOC-questionnaire answers, support-tooling) can consume without re-implementing the "is this user real?" check.
- Half a day back in the Sprint A budget.

## Updated A1 task

```
- Migration 0015: add User.email_verified_at column (nullable, default NULL)
- Backfill: for every existing user, set email_verified_at = User.created_at
  (because every existing user, by induction, signed up via magic-link)
- In verify_magic_link, after marking token consumed:
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
- Test: assert that after a magic-link verify, user.email_verified_at is not None
```

## Reconsider if

- Vibecell ever adds password auth (no magic-link required) — then verification becomes a separate concern.
- We add OAuth-only signup paths (e.g., "sign in with GitHub") that don't pass through email — same caveat.
