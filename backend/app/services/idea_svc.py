"""Idea (workspace inbox) CRUD."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Idea, Project


async def list_ideas(
    db: AsyncSession,
    *,
    workspace_id: str,
    status: str | None = None,
    project_id: str | None = None,
) -> list[Idea]:
    stmt = select(Idea).where(Idea.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Idea.status == status)
    if project_id is not None:
        stmt = stmt.where(Idea.project_id == project_id)
    stmt = stmt.order_by(Idea.captured_at.desc())
    return list((await db.execute(stmt)).scalars())


async def get_idea(db: AsyncSession, *, workspace_id: str, idea_id: str) -> Idea:
    row = (await db.execute(
        select(Idea).where(
            Idea.workspace_id == workspace_id, Idea.id == idea_id
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("idea", idea_id)
    return row


async def create_idea(
    db: AsyncSession,
    *,
    workspace_id: str,
    body: str,
    project_id: str | None = None,
    source: str | None = None,
) -> Idea:
    if project_id is not None:
        # Confirm the project belongs to the workspace before attaching.
        proj = (await db.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )).scalar_one_or_none()
        if proj is None:
            raise ValidationError(detail=f"project {project_id!r} not in workspace")

    row = Idea(
        id=new_ulid(),
        workspace_id=workspace_id,
        project_id=project_id,
        body=body,
        source=source,
    )
    db.add(row)
    await db.flush()
    return row


async def update_idea(
    db: AsyncSession,
    *,
    workspace_id: str,
    idea_id: str,
    status: str | None = None,
    project_id: str | None = None,
    body: str | None = None,
) -> Idea:
    row = await get_idea(db, workspace_id=workspace_id, idea_id=idea_id)
    if status is not None:
        if status not in {"inbox", "triaged", "discarded"}:
            raise ValidationError(detail=f"invalid status {status!r}")
        row.status = status
    if project_id is not None:
        proj = (await db.execute(
            select(Project).where(
                Project.id == project_id, Project.workspace_id == workspace_id
            )
        )).scalar_one_or_none()
        if proj is None:
            raise ValidationError(detail=f"project {project_id!r} not in workspace")
        row.project_id = project_id
        if row.status == "inbox":
            row.status = "triaged"
    if body is not None:
        row.body = body
    await db.flush()
    return row


async def delete_idea(db: AsyncSession, *, workspace_id: str, idea_id: str) -> None:
    row = await get_idea(db, workspace_id=workspace_id, idea_id=idea_id)
    await db.delete(row)
    await db.flush()
