"""Auth routes: magic-link request + verify + logout."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import RateLimitedError
from app.core.middleware import SESSION_COOKIE_NAME, session_cookie_attrs
from app.core.rate_limit import check_and_consume
from app.core.session import delete_session
from app.schemas.auth import MagicLinkAccepted, MagicLinkRequest
from app.services.login import issue_magic_link, verify_magic_link
from app.services.mailer import send_magic_link_email

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
