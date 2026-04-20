"""Passkey (WebAuthn) API — registration + authentication.

Spec 4 — Launch-Enabler. All four endpoints are scaffolded.
Full WebAuthn integration deferred to Spec 4.2 — all return 501 until
WEBAUTHN_RP_ID / webauthn Python package are configured.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.services import passkey as passkey_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/passkey", tags=["passkey"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


class RegistrationFinishBody(BaseModel):
    credential: dict[str, Any]


class AuthBeginBody(BaseModel):
    email: str


class AuthFinishBody(BaseModel):
    email: str
    assertion: dict[str, Any]


# ---------------------------------------------------------------------------
# Registration (requires active session — user must be logged in first)
# ---------------------------------------------------------------------------


@router.post("/register/begin")
async def register_begin(ctx: AuthDep, db: DbDep) -> JSONResponse:
    """Start passkey registration — returns WebAuthn options for navigator.credentials.create().

    Returns 501 until WebAuthn library is configured.
    """
    result = await passkey_svc.start_registration(
        user_id=ctx.user.id,
        user_email=ctx.user.email,
    )
    if result.get("error"):
        return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=result)
    return JSONResponse(content=result)


@router.post("/register/finish")
async def register_finish(
    body: RegistrationFinishBody,
    ctx: AuthDep,
    db: DbDep,
) -> JSONResponse:
    """Complete passkey registration — verifies credential + persists to user.

    Returns 501 until WebAuthn library is configured.
    """
    result = await passkey_svc.finish_registration(
        user_id=ctx.user.id,
        credential_response=body.credential,
    )
    if result.get("error"):
        return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=result)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Authentication (no existing session required)
# ---------------------------------------------------------------------------


@router.post("/auth/begin")
async def auth_begin(body: AuthBeginBody) -> JSONResponse:
    """Start passkey authentication — returns WebAuthn options for navigator.credentials.get().

    Returns 501 until WebAuthn library is configured.
    """
    result = await passkey_svc.start_authentication(email=body.email)
    if result.get("error"):
        return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=result)
    return JSONResponse(content=result)


@router.post("/auth/finish")
async def auth_finish(body: AuthFinishBody, db: DbDep) -> JSONResponse:
    """Complete passkey authentication — verifies assertion + sets session cookie.

    Returns 501 until WebAuthn library is configured.
    """
    result = await passkey_svc.finish_authentication(
        email=body.email,
        assertion_response=body.assertion,
    )
    if result.get("error"):
        return JSONResponse(status_code=status.HTTP_501_NOT_IMPLEMENTED, content=result)
    return JSONResponse(content=result)
