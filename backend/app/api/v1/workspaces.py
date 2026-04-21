"""Workspace CRUD — list, create, get, update."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, WorkspaceContext, require_auth, require_workspace_member
from app.models import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services import presence as presence_svc
from app.services.workspace import create_workspace

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceListItem])
async def list_workspaces(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkspaceListItem]:
    rows = (await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == auth.user.id)
        .order_by(Workspace.created_at.asc())
    )).all()
    return [
        WorkspaceListItem(slug=ws.slug, name=ws.name, role=m.role, plan=ws.plan)
        for ws, m in rows
    ]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: WorkspaceCreate,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceOut:
    ws = await create_workspace(db, owner=auth.user, slug=body.slug, name=body.name)
    await db.commit()
    return WorkspaceOut.model_validate(ws)


@router.get("/{slug}", response_model=WorkspaceOut)
async def get(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
) -> WorkspaceOut:
    return WorkspaceOut.model_validate(ctx.workspace)


@router.patch("/{slug}", response_model=WorkspaceOut)
async def update(
    body: WorkspaceUpdate,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceOut:
    if body.name is not None:
        ctx.workspace.name = body.name
    await db.commit()
    await db.refresh(ctx.workspace)
    return WorkspaceOut.model_validate(ctx.workspace)


@router.get("/me/presence")
async def my_presence(
    auth: Annotated[AuthContext, Depends(require_auth)],
) -> dict:
    """Which projects in my active workspace is Claude live on right now?

    Presence is ephemeral (Redis, 2-minute TTL). A project is "live" if any
    MCP tool call touched it within the last 120 seconds. Poll this endpoint
    every few seconds from the dashboard to show pulsing live indicators.
    """
    ws_id = auth.active_workspace_id
    if ws_id is None:
        return {"entries": []}
    entries = await presence_svc.get_live(ws_id)
    return {"entries": entries}
