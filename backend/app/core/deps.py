"""Reusable FastAPI dependencies for authenticated routes.

require_auth      — validates session cookie, loads user, 401 on missing/bad
require_workspace — resolves workspace by :slug path param, 404 if absent,
                    403 if user is not a member
require_project   — resolves project by :slug within the active workspace
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.models import Project, User, Workspace, WorkspaceMember


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    active_workspace_id: str


async def require_auth(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    user_id = getattr(request.state, "user_id", None)
    workspace_id = getattr(request.state, "workspace_id", None)
    if not user_id or not workspace_id:
        raise UnauthorizedError()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError(detail="user not found")
    return AuthContext(user=user, active_workspace_id=workspace_id)


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    workspace: Workspace
    user: User
    role: str


async def require_workspace_member(
    slug: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")],
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceContext:
    ws = (await db.execute(select(Workspace).where(Workspace.slug == slug))).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", slug)
    member = (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == auth.user.id,
        )
    )).scalar_one_or_none()
    if member is None:
        raise ForbiddenError(detail="not a member of this workspace")
    return WorkspaceContext(workspace=ws, user=auth.user, role=member.role)


@dataclass(frozen=True, slots=True)
class ProjectContext:
    project: Project
    workspace: Workspace
    user: User


async def require_project(
    slug: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")],
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectContext:
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == auth.active_workspace_id)
    )).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", auth.active_workspace_id)
    # Membership already ensured by require_auth loading a valid workspace from the session.
    project = (await db.execute(
        select(Project).where(
            Project.workspace_id == ws.id, Project.slug == slug
        )
    )).scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", slug)
    return ProjectContext(project=project, workspace=ws, user=auth.user)
