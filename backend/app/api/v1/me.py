"""GET /me — return current user, active workspace, and all memberships.

Also hosts the email-change flow (Spec-6 Sprint A2):
  POST /me/change-email           — issue token, mail to NEW address (auth)
  POST /me/change-email/confirm   — verify token, swap user.email
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Workspace, WorkspaceMember
from app.schemas.user import UserOut
from app.schemas.workspace import WorkspaceListItem, WorkspaceOut
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
