"""TOTP 2FA setup + verify + disable.

Three-step lifecycle from the user's perspective:

  1. POST /api/v1/2fa/setup
     → returns {secret, qr_data_uri, otpauth} and stores encrypted
       secret on the user (totp_enabled_at stays NULL until verified).

  2. POST /api/v1/2fa/verify {code}
     → verifies the code against the stored secret. On success, stamps
       totp_enabled_at — only then is 2FA actually enabled. Until then
       /api/v1/2fa/status reports enabled=false.

  3. POST /api/v1/2fa/disable {code}
     → verifies a fresh code (so a stolen session cookie alone can't
       disable 2FA), then clears secret + enabled_at.

The setup endpoint regenerates a fresh secret on every call (overwriting
any pending unconfirmed secret) so users who lose their authenticator
mid-setup can just hit setup again.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import ValidationError
from app.services import totp as totp_svc

router = APIRouter(prefix="/api/v1/2fa", tags=["auth"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


class TotpSetupOut(BaseModel):
    secret: str
    qr_data_uri: str
    otpauth: str


class TotpStatusOut(BaseModel):
    enabled: bool
    enabled_at: str | None = None


class TotpVerifyIn(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


@router.get("/status", response_model=TotpStatusOut)
async def status(auth: AuthDep) -> TotpStatusOut:
    user = auth.user
    return TotpStatusOut(
        enabled=totp_svc.is_enabled(user),
        enabled_at=user.totp_enabled_at.isoformat() if user.totp_enabled_at else None,
    )


@router.post("/setup", response_model=TotpSetupOut)
async def setup(auth: AuthDep, db: DbDep) -> TotpSetupOut:
    """Generate a fresh secret, return QR + provisioning URI. Stored
    encrypted on the user but totp_enabled_at stays NULL until /verify
    confirms the setup."""
    user = auth.user
    secret = totp_svc.generate_secret()
    user.totp_secret_enc = totp_svc.encrypt_secret(secret)
    user.totp_enabled_at = None  # reset confirmation in case a prior
                                  # setup was abandoned.
    await db.flush()
    await db.commit()

    otpauth = totp_svc.otpauth_uri(secret=secret, account_email=user.email)
    qr = totp_svc.qr_data_uri(otpauth=otpauth)
    return TotpSetupOut(secret=secret, qr_data_uri=qr, otpauth=otpauth)


@router.post("/verify", response_model=TotpStatusOut)
async def verify(body: TotpVerifyIn, auth: AuthDep, db: DbDep) -> TotpStatusOut:
    """Verify a code against the stored (unconfirmed) secret. On
    success, stamp enabled_at so future require_admin_2fa checks accept
    codes from this user."""
    user = auth.user
    if not user.totp_secret_enc:
        raise ValidationError(detail="run /2fa/setup first")
    secret = totp_svc.decrypt_secret(user.totp_secret_enc)
    if not totp_svc.verify_code(secret=secret, code=body.code):
        raise ValidationError(detail="invalid code — re-check the time on your authenticator")
    user.totp_enabled_at = datetime.now(UTC)
    await db.flush()
    await db.commit()
    return TotpStatusOut(
        enabled=True, enabled_at=user.totp_enabled_at.isoformat(),
    )


@router.post("/disable", response_model=TotpStatusOut)
async def disable(body: TotpVerifyIn, auth: AuthDep, db: DbDep) -> TotpStatusOut:
    """Disable 2FA by submitting a valid code. We require a fresh code
    here so a stolen session cookie alone can't strip the user's 2FA."""
    user = auth.user
    if not totp_svc.is_enabled(user):
        # Already disabled — idempotent no-op.
        return TotpStatusOut(enabled=False)
    secret = totp_svc.decrypt_secret(user.totp_secret_enc or "")
    if not totp_svc.verify_code(secret=secret, code=body.code):
        raise ValidationError(detail="invalid code")
    user.totp_secret_enc = None
    user.totp_enabled_at = None
    await db.flush()
    await db.commit()
    return TotpStatusOut(enabled=False)
