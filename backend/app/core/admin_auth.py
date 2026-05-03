"""Admin authentication — multi-layer gate for /api/v1/admin/*.

Three layers, ALL must pass:

  1. Standard auth (session cookie valid, user loaded). Inherited via
     require_auth dependency.
  2. Email allowlist — user's email MUST appear in HANGAR_ADMIN_EMAILS
     (comma-separated). Set via /etc/hangar/hangar.env so flipping the
     list requires server filesystem access.
  3. DB flag — user.is_admin MUST be true. Backfilled to true for
     lennystepn@gmail.com in migration 0022; further admins flipped by
     hand in psql.

All three together mean an attacker who manages to compromise ONE layer
(eg. SQL injection that sets is_admin=true on an unrelated user) is
still blocked by the env list, and vice versa.

For write actions, callers additionally depend on `require_admin_2fa`,
which demands a fresh TOTP code (max 30s old per the standard step
window) submitted as the X-Vibecell-2FA header. This means a stolen
session cookie alone CANNOT issue admin writes — physical access to
the user's authenticator device is required for every action.

Every successful admin write is recorded to admin_audit_log via
log_admin_action() so we have an append-only forensic trail.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.ulid import new_ulid
from app.models import AdminAuditLog, User
from app.services import totp as totp_svc


@dataclass(frozen=True, slots=True)
class AdminContext:
    """Request context for admin-only routes. Always carries the auth
    context (so handlers don't need to depend on require_auth separately).
    """
    user: User
    active_workspace_id: str

    @classmethod
    def from_auth(cls, auth: AuthContext) -> AdminContext:
        return cls(user=auth.user, active_workspace_id=auth.active_workspace_id)


def _admin_emails() -> set[str]:
    """Parse HANGAR_ADMIN_EMAILS into a lowercase set."""
    raw = get_settings().admin_emails or ""
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


async def require_admin(
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> AdminContext:
    """Read-only admin gate. Both layers (env list + DB flag) must pass."""
    user = auth.user
    email = (user.email or "").strip().lower()
    allowed = _admin_emails()
    if not email or email not in allowed:
        # Same 403 shape regardless of which layer fails — don't leak
        # which one happened to anyone probing the surface.
        raise ForbiddenError(detail="admin access denied")
    if not user.is_admin:
        raise ForbiddenError(detail="admin access denied")
    return AdminContext.from_auth(auth)


async def require_admin_2fa(
    admin: Annotated[AdminContext, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_vibecell_2fa: Annotated[str | None, Header(alias="X-Vibecell-2FA")] = None,
) -> AdminContext:
    """Write-action admin gate. Adds a TOTP code requirement on top of
    the read gate.

    The frontend collects the code in an action-modal and sends it via
    the X-Vibecell-2FA header. We deliberately don't cache successful
    verifications across requests — every admin write demands a fresh
    code, every time. Yes that's friction; that's the point.

    User must have completed TOTP setup beforehand (totp_enabled_at !=
    null) — we 412 (Precondition Required) if not, with a hint to visit
    /settings to set up.
    """
    user = admin.user
    if not totp_svc.is_enabled(user):
        # Block the write outright — admin actions without 2FA are not
        # acceptable. Use 412 to distinguish "set up 2FA first" from
        # 401/403 (which mean "you're not allowed at all").
        raise UnauthorizedError(detail="admin 2FA required — set up TOTP at /settings/2fa first")

    code = (x_vibecell_2fa or "").strip()
    if not code:
        raise UnauthorizedError(detail="missing X-Vibecell-2FA header")

    secret = totp_svc.decrypt_secret(user.totp_secret_enc or "")
    if not totp_svc.verify_code(secret=secret, code=code):
        raise UnauthorizedError(detail="invalid 2FA code")

    # Reload from DB to make absolutely sure we're not running on a
    # cached object that flipped is_admin in another request — paranoia
    # is cheap on the admin path.
    fresh = (
        await db.execute(select(User).where(User.id == user.id))
    ).scalar_one_or_none()
    if fresh is None or not fresh.is_admin:
        raise ForbiddenError(detail="admin access denied")

    return admin


async def log_admin_action(
    db: AsyncSession,
    *,
    actor: User,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    payload: dict | None = None,
    request: Request | None = None,
) -> None:
    """Append-only audit log entry. Call from every admin write handler
    AFTER the action succeeds (we don't log failed attempts here — those
    are handled by the standard request-level access log).

    Captures actor + IP + UA so post-incident review can correlate with
    other infrastructure logs. payload should be small + structured
    (eg. {"days": 14} for trial-extend, {"coupon_id": "c_xxx"} for
    coupon-create).
    """
    ip: str | None = None
    user_agent: str | None = None
    if request is not None:
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent") or None

    db.add(
        AdminAuditLog(
            id=new_ulid(),
            actor_user_id=actor.id,
            action=action[:64],
            target_type=target_type[:32] if target_type else None,
            target_id=target_id[:128] if target_id else None,
            payload=payload or {},
            ip=ip[:64] if ip else None,
            user_agent=user_agent[:500] if user_agent else None,
        )
    )
    await db.flush()
