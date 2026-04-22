"""Per-project TODO routes — CRUD + batch + start/complete + smart-match."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.todo import (
    TodoBatchIn,
    TodoCompleteIn,
    TodoIn,
    TodoOut,
    TodoUpdate,
)
from app.services import todo_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/todos", tags=["todos"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


@router.get("", response_model=list[TodoOut])
async def list_(
    ctx: CtxDep,
    db: DbDep,
    include_done: Annotated[bool, Query()] = True,
) -> list[TodoOut]:
    rows = await todo_svc.list_todos(
        db, project=ctx.project, include_done=include_done,
    )
    return [TodoOut.model_validate(r) for r in rows]


@router.post("", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
async def create(body: TodoIn, ctx: CtxDep, db: DbDep) -> TodoOut:
    row = await todo_svc.create_todo(
        db,
        project=ctx.project,
        title=body.title,
        body=body.body,
        batch=body.batch,
        position=body.position,
    )
    await db.commit()
    return TodoOut.model_validate(row)


@router.post("/batch", response_model=list[TodoOut], status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: TodoBatchIn, ctx: CtxDep, db: DbDep,
) -> list[TodoOut]:
    rows = await todo_svc.create_batch(
        db,
        project=ctx.project,
        batch=body.batch,
        items=[item.model_dump() for item in body.items],
    )
    await db.commit()
    return [TodoOut.model_validate(r) for r in rows]


@router.patch("/{todo_id}", response_model=TodoOut)
async def patch(
    todo_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: TodoUpdate,
    ctx: CtxDep,
    db: DbDep,
) -> TodoOut:
    row = await todo_svc.update_todo(
        db,
        project=ctx.project,
        todo_id=todo_id,
        **body.model_dump(exclude_unset=True),
    )
    await db.commit()
    return TodoOut.model_validate(row)


@router.post("/{todo_id}/start", response_model=TodoOut)
async def start(
    todo_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> TodoOut:
    row = await todo_svc.start_todo(db, project=ctx.project, todo_id=todo_id)
    await db.commit()
    return TodoOut.model_validate(row)


@router.post("/{todo_id}/complete", response_model=TodoOut)
async def complete(
    todo_id: Annotated[str, Path(min_length=26, max_length=26)],
    body: TodoCompleteIn,
    ctx: CtxDep,
    db: DbDep,
) -> TodoOut:
    row = await todo_svc.complete_todo(
        db,
        project=ctx.project,
        todo_id=todo_id,
        completed_by=body.completed_by,
        completion_note=body.completion_note,
    )
    await db.commit()
    return TodoOut.model_validate(row)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    todo_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> None:
    await todo_svc.delete_todo(db, project=ctx.project, todo_id=todo_id)
    await db.commit()
