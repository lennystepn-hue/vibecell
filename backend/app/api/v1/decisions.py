"""Per-project /decisions routes (ADR-lite)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.decision import DecisionIn, DecisionOut
from app.services import decision_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/decisions", tags=["decisions"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=list[DecisionOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[DecisionOut]:
    rows = await decision_svc.list_decisions(db, project=ctx.project)
    return [DecisionOut.model_validate(r) for r in rows]


@router.post("", response_model=DecisionOut, status_code=status.HTTP_201_CREATED)
async def create(body: DecisionIn, ctx: CtxDep, db: DbDep) -> DecisionOut:
    row = await decision_svc.create_decision(
        db,
        project=ctx.project,
        title=body.title,
        context=body.context,
        decision=body.decision,
        consequences=body.consequences,
        reconsider_if=body.reconsider_if,
    )
    await db.commit()
    return DecisionOut.model_validate(row)


@router.get("/{decision_id}", response_model=DecisionOut)
async def get_(
    decision_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> DecisionOut:
    row = await decision_svc.get_decision(
        db, project=ctx.project, decision_id=decision_id
    )
    return DecisionOut.model_validate(row)


@router.delete("/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    decision_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> None:
    await decision_svc.delete_decision(
        db, project=ctx.project, decision_id=decision_id
    )
    await db.commit()
