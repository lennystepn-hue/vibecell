"""OAuth 2.1 authorization-server endpoints.

Phase 1 scope: POST /oauth/register (DCR per RFC 7591).
Tasks 1.8-1.10 append /authorize, /grant, /deny, /token, /revoke.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.rate_limit import check_and_consume
from app.core.ulid import new_ulid
from app.models import Workspace, WorkspaceMember
from app.oauth import consent
from app.oauth.models import OAuthAuthCode, OAuthClient
from app.oauth.schemas import AuthorizeParams, GrantRequest, RegisterRequest, RegisterResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = await check_and_consume(
        f"oauth:register:{client_ip}",
        capacity=10,
        refill_rate=10 / 60,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    now = datetime.now(timezone.utc)
    client_id = "dyn_" + secrets.token_urlsafe(16)
    row = OAuthClient(
        id=new_ulid(),
        client_id=client_id,
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
        created_at=now,
    )
    db.add(row)
    await db.flush()

    return RegisterResponse(
        client_id=client_id,
        client_id_issued_at=int(now.timestamp()),
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
    )


def _build_redirect_location(redirect_uri: str, **params: str) -> str:
    sep = "&" if "?" in redirect_uri else "?"
    parts = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{redirect_uri}{sep}{parts}"


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    state: str = Query(...),
    scope: str = Query("vibecell:tools"),
    db: AsyncSession = Depends(get_db),
):
    # Validate params via pydantic model
    AuthorizeParams(
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        state=state,
        scope=scope,
    )

    # Client + redirect_uri validation
    client_row = (await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.revoked_at.is_(None),
        )
    )).scalar_one_or_none()
    if not client_row:
        raise HTTPException(400, "invalid_client")
    if redirect_uri not in client_row.redirect_uris:
        raise HTTPException(400, "invalid_redirect_uri")

    # Auth check — user signed in via cookie/bearer?
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        next_url = str(request.url)
        return RedirectResponse(url=f"/login?next={quote(next_url, safe='')}", status_code=302)

    # Stash consent state in Redis
    await consent.store(consent.ConsentState(
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        scope=scope,
        state=state,
        user_id=user_id,
    ))

    # For Phase 1, return JSON for programmatic callers. Phase 3 replaces this with HTML.
    workspaces = (await db.execute(
        select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(
            WorkspaceMember.user_id == user_id
        )
    )).scalars().all()

    return {
        "client_id": client_row.client_id,
        "client_name": client_row.client_name,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "workspaces": [{"id": w.id, "slug": w.slug, "name": w.name} for w in workspaces],
    }


@router.post("/grant")
async def grant(
    body: GrantRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: AsyncSession = Depends(get_db),
):
    cs = await consent.fetch(body.state)
    if cs is None or cs.user_id != auth.user.id:
        raise HTTPException(400, "invalid_state")

    # Verify user membership in chosen workspace
    member = (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == auth.user.id,
            WorkspaceMember.workspace_id == body.workspace_id,
        )
    )).scalar_one_or_none()
    if member is None:
        raise HTTPException(403, "workspace_forbidden")

    # Issue auth code
    code = "c_" + secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    db.add(OAuthAuthCode(
        id=new_ulid(),
        code=code,
        client_id=cs.client_id,
        user_id=auth.user.id,
        workspace_id=body.workspace_id,
        redirect_uri=cs.redirect_uri,
        code_challenge=cs.code_challenge,
        scope=cs.scope,
        expires_at=now + timedelta(seconds=get_settings().oauth_auth_code_ttl_seconds),
    ))
    await db.flush()
    await consent.drop(body.state)

    return RedirectResponse(
        url=_build_redirect_location(cs.redirect_uri, code=code, state=cs.state),
        status_code=302,
    )


@router.post("/deny")
async def deny(
    body: GrantRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    cs = await consent.fetch(body.state)
    if cs is None or cs.user_id != auth.user.id:
        raise HTTPException(400, "invalid_state")
    await consent.drop(body.state)
    return RedirectResponse(
        url=_build_redirect_location(cs.redirect_uri, error="access_denied", state=cs.state),
        status_code=302,
    )
