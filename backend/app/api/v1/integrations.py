"""Integrations listing + GitHub OAuth flow."""
from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import HangarError, NotFoundError
from app.core.redis import get_redis
from app.schemas.integration import IntegrationOut
from app.services import github as github_svc
from app.services import integration as integ_svc

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]

_OAUTH_STATE_TTL = 600  # 10 minutes


def _oauth_redirect_uri() -> str:
    base = get_settings().base_url
    return urljoin(base + "/", "api/v1/integrations/github/oauth-callback")


@router.get("", response_model=list[IntegrationOut])
async def list_(auth: AuthDep, db: DbDep) -> list[IntegrationOut]:
    rows = await integ_svc.list_integrations(db, workspace_id=auth.active_workspace_id)
    return [
        IntegrationOut(
            id=r.id,
            kind=r.kind,
            connected_at=r.connected_at,
            config=integ_svc.mask_config(r.config or {}),
        )
        for r in rows
    ]


@router.get("/github/oauth-start")
async def github_oauth_start(auth: AuthDep) -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    redis = await get_redis()
    await redis.set(
        f"gh-oauth-state:{state}",
        f"{auth.active_workspace_id}:{auth.user.id}",
        ex=_OAUTH_STATE_TTL,
    )
    url = github_svc.authorize_url(state=state, redirect_uri=_oauth_redirect_uri())
    return RedirectResponse(url=url, status_code=302)


@router.get("/github/oauth-callback")
async def github_oauth_callback(
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    request: Request,
    db: DbDep,
) -> RedirectResponse:
    redis = await get_redis()
    key = f"gh-oauth-state:{state}"
    stored = await redis.get(key)
    if not stored:
        raise HangarError(
            title="OAuth state invalid or expired",
            status=400, type_="/errors/oauth-state",
        )
    await redis.delete(key)

    workspace_id, user_id = stored.split(":", 1)

    # Optional cross-check: the current session must match the starting user.
    session_user_id = getattr(request.state, "user_id", None)
    if session_user_id and session_user_id != user_id:
        raise HangarError(
            title="OAuth state user mismatch",
            status=400, type_="/errors/oauth-state",
        )

    access_token = await github_svc.exchange_code(
        code=code, redirect_uri=_oauth_redirect_uri(),
    )
    me = await github_svc.me(access_token)
    login = me.get("login")

    await integ_svc.upsert_integration(
        db,
        workspace_id=workspace_id,
        kind="github",
        raw_token=access_token,
        config={"login": login, "avatar_url": me.get("avatar_url")},
    )
    await db.commit()

    return RedirectResponse(url="/import/github", status_code=303)


@router.delete("/github", status_code=204)
async def delete_github(auth: AuthDep, db: DbDep) -> None:
    try:
        await integ_svc.delete_integration(
            db, workspace_id=auth.active_workspace_id, kind="github",
        )
    except NotFoundError:
        return
    await db.commit()
