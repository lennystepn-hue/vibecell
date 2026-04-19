"""Per-project /notes (singleton markdown scratchpad)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.note import NoteOut, NoteUpdate
from app.services import note_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/notes", tags=["notes"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=NoteOut)
async def get(ctx: CtxDep, db: DbDep) -> NoteOut:
    row = await note_svc.get_note(db, project=ctx.project)
    if row is None:
        return NoteOut()
    return NoteOut.model_validate(row)


@router.put("", response_model=NoteOut)
async def put(body: NoteUpdate, ctx: CtxDep, db: DbDep) -> NoteOut:
    row = await note_svc.upsert_note(
        db, project=ctx.project, markdown=body.markdown
    )
    await db.commit()
    return NoteOut.model_validate(row)
