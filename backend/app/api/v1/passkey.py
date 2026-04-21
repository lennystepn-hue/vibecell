"""Passkey (WebAuthn) API — registration + authentication.

Spec 4.2 — Launch-Enabler. Real WebAuthn implementation via py_webauthn.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.middleware import session_cookie_attrs
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
async def register_begin(ctx: AuthDep) -> JSONResponse:
    """Start passkey registration — returns WebAuthn options for navigator.credentials.create()."""
    options = await passkey_svc.start_registration(
        user_id=ctx.user.id,
        user_email=ctx.user.email,
    )
    return JSONResponse(content=options)


@router.post("/register/finish")
async def register_finish(
    body: RegistrationFinishBody,
    ctx: AuthDep,
) -> JSONResponse:
    """Complete passkey registration — verifies credential + persists to user."""
    await passkey_svc.finish_registration(
        user_id=ctx.user.id,
        credential_response=body.credential,
    )
    return JSONResponse(content={"ok": True})


# ---------------------------------------------------------------------------
# Authentication (no existing session required)
# ---------------------------------------------------------------------------


@router.post("/auth/begin")
async def auth_begin(body: AuthBeginBody) -> JSONResponse:
    """Start passkey authentication — returns WebAuthn options for navigator.credentials.get()."""
    options = await passkey_svc.start_authentication(email=body.email)
    return JSONResponse(content=options)


@router.post("/auth/finish")
async def auth_finish(body: AuthFinishBody) -> JSONResponse:
    """Complete passkey authentication — verifies assertion + sets session cookie."""
    session_id = await passkey_svc.finish_authentication(
        email=body.email,
        assertion_response=body.assertion,
    )
    response = JSONResponse(content={"ok": True})
    response.set_cookie(value=session_id, **session_cookie_attrs())  # type: ignore[arg-type]
    return response
