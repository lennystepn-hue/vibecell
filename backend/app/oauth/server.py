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
from app.metrics.registry import oauth_authorize_outcomes, oauth_tokens_issued
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

    # Programmatic callers (Accept: application/json) get JSON directly.
    # Browser callers are redirected to the SPA consent page.
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
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

    # Browser: redirect to the SPA consent page
    return RedirectResponse(url=f"/oauth/consent?state={quote(state, safe='')}", status_code=302)


@router.get("/consent-context")
async def consent_context(
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Return stashed consent context as JSON for the SPA consent page."""
    cs = await consent.fetch(state)
    if cs is None:
        raise HTTPException(404, "state_not_found")

    workspaces = (await db.execute(
        select(Workspace).join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id).where(
            WorkspaceMember.user_id == cs.user_id
        )
    )).scalars().all()

    client_row = (await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == cs.client_id)
    )).scalar_one_or_none()

    return {
        "client_id": cs.client_id,
        "client_name": client_row.client_name if client_row else None,
        "redirect_uri": cs.redirect_uri,
        "scope": cs.scope,
        "state": cs.state,
        "workspaces": [{"id": w.id, "slug": w.slug, "name": w.name} for w in workspaces],
    }


@router.post("/grant")
async def grant(
    request: Request,
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

    redirect_url = _build_redirect_location(cs.redirect_uri, code=code, state=cs.state)

    oauth_authorize_outcomes.labels(outcome="granted").inc()

    # SPA calls with Accept: application/json — return JSON so the frontend can
    # do window.location.href = data.redirect (avoids opaque-redirect headaches).
    if "application/json" in request.headers.get("accept", ""):
        return {"redirect": redirect_url}

    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/deny")
async def deny(
    request: Request,
    body: GrantRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
):
    cs = await consent.fetch(body.state)
    if cs is None or cs.user_id != auth.user.id:
        raise HTTPException(400, "invalid_state")
    await consent.drop(body.state)

    redirect_url = _build_redirect_location(cs.redirect_uri, error="access_denied", state=cs.state)

    oauth_authorize_outcomes.labels(outcome="denied").inc()

    if "application/json" in request.headers.get("accept", ""):
        return {"redirect": redirect_url}

    return RedirectResponse(url=redirect_url, status_code=302)


# ---------------------------------------------------------------------------
# Task 1.9 — POST /oauth/token
# ---------------------------------------------------------------------------
import base64  # noqa: E402 — appended block; stdlib, no ordering issue
import hashlib  # noqa: E402

from fastapi import Form  # noqa: E402

from app.oauth.models import OAuthAccessToken, OAuthRefreshToken  # noqa: E402
from app.oauth.tokens import (  # noqa: E402
    OAuthTokenClaims,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
)


@router.post("/token")
async def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    client_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    allowed, retry_after = await check_and_consume(
        f"oauth:token:{client_id}", capacity=20, refill_rate=20 / 60,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limited", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    if grant_type == "authorization_code":
        return await _token_from_code(db, code, redirect_uri, code_verifier, client_id)
    if grant_type == "refresh_token":
        return await _token_from_refresh(db, refresh_token, client_id)
    raise HTTPException(400, detail={"error": "unsupported_grant_type"})


def _verify_pkce(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return secrets.compare_digest(expected, challenge)


async def _token_from_code(
    db: AsyncSession,
    code: str | None,
    redirect_uri: str | None,
    code_verifier: str | None,
    client_id: str,
):
    if not (code and redirect_uri and code_verifier):
        raise HTTPException(400, detail={"error": "invalid_request"})

    row = (await db.execute(
        select(OAuthAuthCode).where(OAuthAuthCode.code == code)
    )).scalar_one_or_none()
    if row is None or row.consumed_at is not None:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.client_id != client_id:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.redirect_uri != redirect_uri:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if not _verify_pkce(code_verifier, row.code_challenge):
        raise HTTPException(400, detail={"error": "invalid_grant"})

    now = datetime.now(timezone.utc)
    row.consumed_at = now
    s = get_settings()

    jwt_str, jti = issue_access_token(OAuthTokenClaims(
        sub=row.user_id, client_id=row.client_id, workspace_id=row.workspace_id, scope=row.scope,
    ))
    family_id = new_ulid()
    db.add(OAuthAccessToken(
        id=new_ulid(), jti=jti, client_id=row.client_id, user_id=row.user_id,
        workspace_id=row.workspace_id, scope=row.scope, issued_from_refresh_family=family_id,
        issued_at=now, expires_at=now + timedelta(seconds=s.oauth_access_token_ttl_seconds),
    ))

    rt_value = issue_refresh_token()
    db.add(OAuthRefreshToken(
        id=new_ulid(), token_hash=hash_refresh_token(rt_value), family_id=family_id,
        client_id=row.client_id, user_id=row.user_id, workspace_id=row.workspace_id,
        scope=row.scope, issued_at=now,
        expires_at=now + timedelta(seconds=s.oauth_refresh_token_ttl_seconds),
    ))

    client_row = (await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == row.client_id)
    )).scalar_one()
    if client_row.registered_by_user_id is None:
        client_row.registered_by_user_id = row.user_id
    client_row.last_used_at = now

    await db.flush()

    oauth_tokens_issued.labels(client_name=client_row.client_name or "unknown").inc()

    return {
        "access_token": jwt_str,
        "token_type": "Bearer",
        "expires_in": s.oauth_access_token_ttl_seconds,
        "refresh_token": rt_value,
        "scope": row.scope,
    }


async def _token_from_refresh(db: AsyncSession, refresh_token: str | None, client_id: str):
    if not refresh_token:
        raise HTTPException(400, detail={"error": "invalid_request"})

    h = hash_refresh_token(refresh_token)
    row = (await db.execute(
        select(OAuthRefreshToken).where(OAuthRefreshToken.token_hash == h)
    )).scalar_one_or_none()
    if row is None or row.consumed_at is not None or row.revoked_at is not None:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.client_id != client_id:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, detail={"error": "invalid_grant"})

    now = datetime.now(timezone.utc)
    row.consumed_at = now
    s = get_settings()

    jwt_str, jti = issue_access_token(OAuthTokenClaims(
        sub=row.user_id, client_id=row.client_id, workspace_id=row.workspace_id, scope=row.scope,
    ))
    db.add(OAuthAccessToken(
        id=new_ulid(), jti=jti, client_id=row.client_id, user_id=row.user_id,
        workspace_id=row.workspace_id, scope=row.scope, issued_from_refresh_family=row.family_id,
        issued_at=now, expires_at=now + timedelta(seconds=s.oauth_access_token_ttl_seconds),
    ))

    new_rt = issue_refresh_token()
    db.add(OAuthRefreshToken(
        id=new_ulid(), token_hash=hash_refresh_token(new_rt), family_id=row.family_id,
        client_id=row.client_id, user_id=row.user_id, workspace_id=row.workspace_id,
        scope=row.scope, issued_at=now,
        expires_at=now + timedelta(seconds=s.oauth_refresh_token_ttl_seconds),
    ))

    client_row = (await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == row.client_id)
    )).scalar_one_or_none()
    client_name = (client_row.client_name if client_row else None) or "unknown"

    await db.flush()

    oauth_tokens_issued.labels(client_name=client_name).inc()

    return {
        "access_token": jwt_str,
        "token_type": "Bearer",
        "expires_in": s.oauth_access_token_ttl_seconds,
        "refresh_token": new_rt,
        "scope": row.scope,
    }


# ---------------------------------------------------------------------------
# Task 1.10 — POST /oauth/revoke (RFC 7009)
# ---------------------------------------------------------------------------
from fastapi import Response  # noqa: E402

from app.oauth.tokens import JTIBlacklist, verify_access_token  # noqa: E402


@router.post("/revoke")
async def revoke(
    token: str = Form(...),
    token_type_hint: str = Form("access_token"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # RFC 7009: return 200 regardless of token validity
    try:
        if token_type_hint == "refresh_token":
            await _revoke_refresh(db, token)
        else:
            await _revoke_access(db, token)
    except Exception:  # noqa: BLE001 — intentional broad swallow per RFC
        pass
    return Response(status_code=200)


async def _revoke_access(db: AsyncSession, token: str) -> None:
    try:
        claims = verify_access_token(token)
    except ValueError:
        return
    ttl = max(1, claims.exp - int(datetime.now(timezone.utc).timestamp()))
    await JTIBlacklist().add(claims.jti, ttl_seconds=ttl)
    row = (await db.execute(
        select(OAuthAccessToken).where(OAuthAccessToken.jti == claims.jti)
    )).scalar_one_or_none()
    if row:
        row.revoked_at = datetime.now(timezone.utc)


async def _revoke_refresh(db: AsyncSession, token: str) -> None:
    h = hash_refresh_token(token)
    row = (await db.execute(
        select(OAuthRefreshToken).where(OAuthRefreshToken.token_hash == h)
    )).scalar_one_or_none()
    if row is None:
        return
    now = datetime.now(timezone.utc)
    row.revoked_at = now
    # Cascade: revoke all access tokens in same family still valid
    access_rows = (await db.execute(
        select(OAuthAccessToken).where(
            OAuthAccessToken.issued_from_refresh_family == row.family_id,
            OAuthAccessToken.revoked_at.is_(None),
            OAuthAccessToken.expires_at > now,
        )
    )).scalars().all()
    for ar in access_rows:
        ar.revoked_at = now
        ttl = max(1, int(ar.expires_at.timestamp()) - int(now.timestamp()))
        await JTIBlacklist().add(ar.jti, ttl_seconds=ttl)

    # Also invalidate the refresh token itself if not yet blacklisted (blocks reuse)
    # (covered by revoked_at check in _token_from_refresh)
