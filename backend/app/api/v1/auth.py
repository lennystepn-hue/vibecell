"""Auth routes: magic-link request + verify + Google Sign-In + logout."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, Query, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import RateLimitedError
from app.core.middleware import SESSION_COOKIE_NAME, session_cookie_attrs
from app.core.rate_limit import check_and_consume
from app.core.session import SessionPayload, create_session, delete_session
from app.schemas.auth import MagicLinkAccepted, MagicLinkRequest
from app.services import google_oauth
from app.services.login import (
    issue_magic_link,
    login_or_bootstrap_user,
    verify_magic_link,
)
from app.services.mailer import send_magic_link_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_DbDep = Annotated[AsyncSession, Depends(get_db)]


@router.post("/magic-link", status_code=202, response_model=MagicLinkAccepted)
async def request_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: _DbDep,
) -> MagicLinkAccepted:
    email = body.email.lower()

    # Rate limit: 3/hour per email, 10/hour per IP
    ip = request.client.host if request.client else "unknown"
    email_key = f"rl:auth:email:{email}"
    ip_key = f"rl:auth:ip:{ip}"

    email_ok, retry_email = await check_and_consume(email_key, capacity=3, refill_rate=3 / 3600)
    ip_ok, retry_ip = await check_and_consume(ip_key, capacity=10, refill_rate=10 / 3600)
    if not email_ok:
        raise RateLimitedError(detail="too many requests for this email", retry_after_s=retry_email)
    if not ip_ok:
        raise RateLimitedError(detail="too many requests from this IP", retry_after_s=retry_ip)

    # Always respond 202 (no user enumeration) — issue the link anyway,
    # even if we have no users for this address yet (first-login bootstrap
    # runs on verify).
    raw_token = await issue_magic_link(db, email=email)
    await db.commit()

    verify_url = f"{get_settings().base_url}/auth/verify?token={raw_token}"
    await send_magic_link_email(to=email, verify_url=verify_url)

    return MagicLinkAccepted()


@router.get("/verify")
async def verify(
    token: str,
    db: _DbDep,
) -> RedirectResponse:
    session_id = await verify_magic_link(db, raw_token=token)
    await db.commit()
    # Freshly-authenticated users land on the dashboard, not the marketing
    # landing page. / now serves the anon marketing page for everyone.
    response = RedirectResponse(url="/p", status_code=303)
    response.set_cookie(
        value=session_id,
        **session_cookie_attrs(),  # type: ignore[arg-type]
    )
    return response


@router.post("/logout")
async def logout(
    hangar_session: str | None = Cookie(default=None),
) -> Response:
    if hangar_session:
        await delete_session(hangar_session)
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp


# ---------------------------------------------------------------------------
# Google Sign-In
# ---------------------------------------------------------------------------

@router.get("/google/start")
async def google_start(
    request: Request,
    next: Annotated[str | None, Query(max_length=200)] = None,
) -> RedirectResponse:
    """Kick off the Google OAuth flow. The frontend's "Sign in with Google"
    button just navigates here — we generate state + PKCE, store them in
    Redis, and 302 the browser to Google's consent screen."""
    if not google_oauth.is_configured():
        # Frontend hides the button when /google/configured returns false,
        # but defend in depth in case someone hits the URL directly.
        return RedirectResponse(
            url="/login?err=google_not_configured", status_code=303,
        )

    # Light per-IP rate limit so a hostile client can't burn through Redis
    # state slots. Same shape as magic-link's IP limit.
    ip = request.client.host if request.client else "unknown"
    ip_ok, retry_ip = await check_and_consume(
        f"rl:auth:ip:{ip}", capacity=10, refill_rate=10 / 3600,
    )
    if not ip_ok:
        raise RateLimitedError(
            detail="too many auth requests from this IP", retry_after_s=retry_ip,
        )

    try:
        url = await google_oauth.begin(next_path=next)
    except google_oauth.GoogleOAuthError as exc:
        logger.warning("google_oauth.begin failed: %s", exc)
        return RedirectResponse(url="/login?err=google_failed", status_code=303)
    return RedirectResponse(url=url, status_code=303)


@router.get("/google/callback")
async def google_callback(
    db: _DbDep,
    code: Annotated[str | None, Query(max_length=512)] = None,
    state: Annotated[str | None, Query(max_length=128)] = None,
    error: Annotated[str | None, Query(max_length=128)] = None,
) -> RedirectResponse:
    """Google redirects here after the user consents (or bails). We trade
    the code for tokens, fetch their email, and either sign them in
    (existing user) or bootstrap a fresh user + workspace + trial sub.

    Result either way: a session cookie set + redirect to the page the
    user originally wanted (or /p)."""
    # User-cancelled or upstream error.
    if error:
        logger.info("google_callback: user/google reported error=%s", error)
        return RedirectResponse(
            url=f"/login?err=google_{quote(error[:40])}", status_code=303,
        )
    if not code or not state:
        return RedirectResponse(url="/login?err=google_no_code", status_code=303)

    try:
        email, next_path = await google_oauth.consume(state=state, code=code)
    except google_oauth.GoogleOAuthError as exc:
        logger.warning("google_callback: consume failed: %s", exc)
        return RedirectResponse(url="/login?err=google_failed", status_code=303)

    user, workspace = await login_or_bootstrap_user(db, email=email)
    # Google guarantees verified email when email_verified is true (we
    # check that in google_oauth.consume), so mirror magic-link's
    # email_verified_at semantics.
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(UTC)
    await db.flush()
    await db.commit()

    session_id = await create_session(
        SessionPayload(user_id=user.id, workspace_id=workspace.id),
        ttl_seconds=get_settings().session_max_age,
    )
    response = RedirectResponse(url=next_path, status_code=303)
    response.set_cookie(
        value=session_id,
        **session_cookie_attrs(),  # type: ignore[arg-type]
    )
    return response


@router.get("/google/configured")
async def google_configured() -> dict[str, bool]:
    """Surface whether Google login is wired up so the frontend can
    conditionally render the button. Public — no secrets leaked, just
    a bool."""
    return {"configured": google_oauth.is_configured()}
