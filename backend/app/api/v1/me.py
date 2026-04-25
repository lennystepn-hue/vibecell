"""GET /me — return current user, active workspace, and all memberships.

Also hosts the email-change flow (Spec-6 Sprint A2):
  POST /me/change-email           — issue token, mail to NEW address (auth)
  POST /me/change-email/confirm   — verify token, swap user.email

And the GDPR data-export + account-delete (Spec-6 Sprint A3):
  GET  /me/export    — JSON dump of every row owned by the user
  DELETE /me         — purge user + solely-owned workspaces (refuses if
                       any owned workspace has co-members)
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import ValidationError
from app.core.middleware import SESSION_COOKIE_NAME
from app.core.session import delete_session
from app.models import Plan, Subscription, Workspace, WorkspaceMember
from app.schemas.user import UserOut
from app.schemas.workspace import WorkspaceListItem, WorkspaceOut
from app.services import account_purge
from app.services import email_change as email_change_svc
from app.services.mailer import send_email_change_email

router = APIRouter(prefix="/api/v1", tags=["me"])


class MeOut(BaseModel):
    user: UserOut
    active_workspace: WorkspaceOut
    workspaces: list[WorkspaceListItem]


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr


class ChangeEmailConfirmRequest(BaseModel):
    token: str


class ChangeEmailAccepted(BaseModel):
    """Always returned on /me/change-email — never reveals whether the address
    was actually issued (avoids email-enumeration). The body is informational
    only; the real signal is whether the user receives a mail."""
    accepted: bool = True


class DeleteAccountRequest(BaseModel):
    """Type the current email to confirm — guards against accidental clicks."""
    confirmation: EmailStr


class SubscriptionOut(BaseModel):
    """Spec-6 Sprint B4 — surface the user's subscription state to the
    /settings/billing page + the global TrialBanner."""
    status: str
    plan_slug: str
    plan_name: str
    monthly_price_eur_cents: int
    trial_ends_at: str | None
    current_period_end: str | None
    cancel_at_period_end: bool


@router.get("/me", response_model=MeOut)
async def me(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeOut:
    active_ws = (await db.execute(
        select(Workspace).where(Workspace.id == auth.active_workspace_id)
    )).scalar_one()

    rows = (await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == auth.user.id)
        .order_by(Workspace.created_at.asc())
    )).all()

    workspaces = [
        WorkspaceListItem(slug=ws.slug, name=ws.name, role=m.role, plan=ws.plan)
        for ws, m in rows
    ]
    return MeOut(
        user=UserOut.model_validate(auth.user),
        active_workspace=WorkspaceOut.model_validate(active_ws),
        workspaces=workspaces,
    )


@router.post("/me/change-email", status_code=202, response_model=ChangeEmailAccepted)
async def change_email_request(
    body: ChangeEmailRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChangeEmailAccepted:
    """Issue a token + mail it to the new address. Returns 202 even on
    validation errors of the addressee (don't expose whether an email is
    taken — clients learn through the email arriving or not arriving)."""
    try:
        raw_token = await email_change_svc.issue_email_change_token(
            db, user=auth.user, new_email=body.new_email
        )
    except Exception:
        # Soft-fail: still return 202 to avoid enumeration. The client never
        # learns more than "we accepted your request" — they confirm via the
        # link arriving in the new mailbox.
        await db.rollback()
        return ChangeEmailAccepted()

    await db.commit()
    confirm_url = f"{get_settings().base_url}/auth/change-email/{raw_token}"
    await send_email_change_email(to=body.new_email, confirm_url=confirm_url)
    return ChangeEmailAccepted()


@router.post("/me/change-email/confirm", response_model=UserOut)
async def change_email_confirm(
    body: ChangeEmailConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    """Consume the token sent to the new address. Swaps user.email,
    invalidates pending magic-link tokens for the OLD address. Returns the
    updated user. The client should refresh /me afterwards.

    Intentionally NOT auth-protected — the user may click the link in a
    different browser / device than they're signed in on. Token possession
    is the proof.
    """
    user = await email_change_svc.confirm_email_change(db, raw_token=body.token)
    await db.commit()
    return UserOut.model_validate(user)


@router.get("/me/export")
async def export_my_data(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """GDPR Art. 20 — data portability. Returns every row owned by the
    user across every table as a single JSON document. Synchronous — fine
    for current dataset sizes (max ~1MB per user). If it ever gets slow,
    move to an async job that emails the user a download link."""
    payload = await account_purge.gather_user_data(db, auth.user.id)
    body = json.dumps(payload, indent=2, default=str)
    return Response(
        content=body,
        media_type="application/json",
        headers={
            "Content-Disposition": (
                f'attachment; filename="vibecell-export-{auth.user.id}.json"'
            ),
        },
    )


@router.get("/me/subscription", response_model=SubscriptionOut)
async def my_subscription(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SubscriptionOut:
    """Return the current user's subscription state. Drives the
    /settings/billing page and the global trial banner."""
    sub = (
        await db.execute(
            select(Subscription).where(Subscription.user_id == auth.user.id)
        )
    ).scalar_one_or_none()
    if sub is None:
        # Should be impossible after B1 bootstrap — surface as 500-ish hint
        # rather than 404 so support knows to investigate.
        raise ValidationError(detail="user has no subscription row")
    plan = await db.get(Plan, sub.plan_id)
    if plan is None:
        raise ValidationError(detail="subscription points at non-existent plan")
    return SubscriptionOut(
        status=sub.status,
        plan_slug=plan.slug,
        plan_name=plan.name,
        monthly_price_eur_cents=plan.monthly_price_eur_cents,
        trial_ends_at=sub.trial_ends_at.isoformat() if sub.trial_ends_at else None,
        current_period_end=(
            sub.current_period_end.isoformat() if sub.current_period_end else None
        ),
        cancel_at_period_end=sub.cancel_at_period_end,
    )


@router.delete("/me", status_code=204)
async def delete_my_account(
    body: DeleteAccountRequest,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    hangar_session: Annotated[str | None, Cookie()] = None,
) -> Response:
    """GDPR Art. 17 — right to erasure. Permanently deletes the user
    account + all solely-owned data. Refuses with 409 if the user owns a
    workspace with co-members.

    Requires the body to contain `confirmation` matching the user's
    current email — guards against accidental DELETE requests fired by
    bad client code or browser extensions.
    """
    if body.confirmation.lower() != auth.user.email.lower():
        raise ValidationError(detail="confirmation must match your current email")

    await account_purge.purge(db, auth.user.id)
    await db.commit()

    # Burn the current session cookie so the user is logged out immediately.
    if hangar_session:
        await delete_session(hangar_session)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
