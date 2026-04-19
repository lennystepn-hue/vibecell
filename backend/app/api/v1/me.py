"""GET /me — return current user, active workspace, and all memberships."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Workspace, WorkspaceMember
from app.schemas.user import UserOut
from app.schemas.workspace import WorkspaceListItem, WorkspaceOut

router = APIRouter(prefix="/api/v1", tags=["me"])


class MeOut(BaseModel):
    user: UserOut
    active_workspace: WorkspaceOut
    workspaces: list[WorkspaceListItem]


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
