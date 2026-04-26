"""Spec-6 — global write-gate middleware.

Runs after the SessionMiddleware. For every write request (POST/PATCH/PUT)
made by an authenticated user, looks up the user's access_level. If
read-only, returns 402 Payment Required with a Problem+JSON body pointing
at /settings/billing.

Why a middleware instead of a per-endpoint Depends() dependency:

  - New write endpoints land protected by default. The bug shape we want
    to prevent is "we forgot to add the dependency on /api/v1/something
    that mutates state, so non-paying users could keep writing free
    content via that route." With a middleware, the protection is opt-out
    (via EXEMPT_PATHS) instead of opt-in.

  - The MCP endpoint has its OWN gate inside the JSON-RPC dispatcher
    (server.py) — different protocol, different error-code shape — so
    /mcp is exempted here.

  - DELETE requests are intentionally NOT blocked — read-only users keep
    the right to remove their own data, even if they can't add more.
    Cleanup is part of the exit path.

EXEMPT_PATHS exists for the GDPR / billing / auth surfaces that MUST keep
working even when the subscription is dead — otherwise a user with an
expired card couldn't pay to fix it.
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.db import session_scope
from app.services.access_level import access_level_for_user

# HTTP methods that mutate state. Anything not in this set bypasses the
# gate (GETs, HEADs, OPTIONS, DELETEs).
_WRITE_METHODS = frozenset({"POST", "PATCH", "PUT"})

# Path prefixes that ALWAYS work, even for read-only users. Order doesn't
# matter — we use startswith.
_EXEMPT_PREFIXES: tuple[str, ...] = (
    # Billing surfaces — must stay reachable so the user can renew.
    "/api/v1/billing/",
    # Auth lifecycle — login, magic-link, logout. Without these, a
    # read-only user who logs out can never log back in.
    "/api/v1/auth/",
    "/oauth/",
    # /me read + email-change confirm + GDPR export + delete are exempt
    # from the gate. The export/delete endpoints implement Articles 17
    # and 20 of GDPR — refusing them is illegal.
    "/api/v1/me",
    # MCP has its own gate (see app/mcp/server.py — _dispatch_tool_call
    # uses tool.is_write + access_level_for_user). Exempt here so we
    # don't double-check.
    "/api/v1/mcp",
    "/mcp",
    # Health + metrics are infrastructure-side.
    "/api/v1/healthz",
    "/api/v1/metrics",
    # Webhooks come from third parties (Stripe). Not user-scoped.
    "/api/v1/billing/webhook",
)


def _is_exempt(path: str) -> bool:
    return any(path.startswith(p) for p in _EXEMPT_PREFIXES)


def _problem_response() -> Response:
    body = {
        "type": "/errors/subscription-inactive",
        "title": "Payment Required",
        "status": 402,
        "detail": "Subscription expired — Vibecell is read-only. "
                  "Renew to keep writing.",
        "upgrade_url": "/settings/billing",
    }
    return Response(
        content=json.dumps(body),
        status_code=402,
        media_type="application/problem+json",
    )


class PlanGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Fast paths first — keep the middleware cheap on read traffic.
        if request.method not in _WRITE_METHODS:
            return await call_next(request)
        if _is_exempt(request.url.path):
            return await call_next(request)

        # SessionMiddleware ran before us and either set request.state.user_id
        # or didn't (anonymous request). Anonymous writes never reach
        # the handler anyway (require_auth raises 401), so we let them
        # through without a DB hit.
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            return await call_next(request)

        async with session_scope() as db:
            level = await access_level_for_user(db, user_id)
        if level != "full":
            return _problem_response()

        return await call_next(request)


def install_plan_gate_middleware(app: FastAPI) -> None:
    app.add_middleware(PlanGateMiddleware)
