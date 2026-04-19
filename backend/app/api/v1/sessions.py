"""Per-project /sessions routes (coding blocks)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.session import (
    SessionIn,
    SessionListPage,
    SessionOut,
    SessionUpdate,
)
from app.services import session_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/sessions", tags=["sessions"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=SessionListPage)
async def list_(
    ctx: CtxDep,
    db: DbDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> SessionListPage:
    items, next_cursor = await session_svc.list_sessions(
        db, project=ctx.project, cursor=cursor, limit=limit
    )
    return SessionListPage(
        items=[SessionOut.model_validate(r) for r in items],
        next_cursor=next_cursor,
    )


@router.post("", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
async def create(body: SessionIn, ctx: CtxDep, db: DbDep) -> SessionOut:
    row = await session_svc.create_session(
        db,
        project=ctx.project,
        started_at=body.started_at,
        ended_at=body.ended_at,
        summary=body.summary,
        files_touched=body.files_touched,
        commits=body.commits,
        next_step=body.next_step,
        source=body.source,
    )
    await db.commit()
    return SessionOut.model_validate(row)


@router.patch("/{session_id}", response_model=SessionOut)
async def patch(
    session_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: SessionUpdate,
    ctx: CtxDep,
    db: DbDep,
) -> SessionOut:
    row = await session_svc.update_session(
        db,
        project=ctx.project,
        session_id=session_id,
        **body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return SessionOut.model_validate(row)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    session_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> None:
    await session_svc.delete_session(
        db, project=ctx.project, session_id=session_id
    )
    await db.commit()
