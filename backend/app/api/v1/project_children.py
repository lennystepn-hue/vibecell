"""Sub-resource routes under /api/v1/projects/{slug}/*."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.schemas.project import (
    CommandIn,
    CommandOut,
    CommandUpdate,
    ContextOut,
    ContextUpsert,
    EnvironmentIn,
    EnvironmentOut,
    EnvironmentUpdate,
    InfraOut,
    InfraUpsert,
    LinkIn,
    LinkOut,
    LinkUpdate,
    RepoIn,
    RepoOut,
    StackAttachIn,
    StackOut,
    TagAttachIn,
    TagOut,
)
from app.services import project_children as svc

router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["project-children"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


# ---------- context ----------

@router.get("/context", response_model=ContextOut)
async def get_context(ctx: CtxDep, db: DbDep) -> ContextOut:
    row = await svc.get_context(db, ctx.project)
    if row is None:
        return ContextOut()
    return ContextOut.model_validate(row)


@router.patch("/context", response_model=ContextOut)
async def patch_context(body: ContextUpsert, ctx: CtxDep, db: DbDep) -> ContextOut:
    row = await svc.upsert_context(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return ContextOut.model_validate(row)


# ---------- repos ----------

@router.post("/repos", response_model=RepoOut, status_code=status.HTTP_201_CREATED)
async def create_repo(body: RepoIn, ctx: CtxDep, db: DbDep) -> RepoOut:
    repo = await svc.add_repo(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return RepoOut.model_validate(repo)


@router.patch("/repos/{repo_id}", response_model=RepoOut)
async def patch_repo(
    repo_id: Annotated[str, Path(min_length=1)],
    body: RepoIn,
    ctx: CtxDep,
    db: DbDep,
) -> RepoOut:
    repo = await svc.update_repo(db, ctx.project, repo_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return RepoOut.model_validate(repo)


@router.delete("/repos/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(repo_id: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.delete_repo(db, ctx.project, repo_id)
    await db.commit()


# ---------- environments ----------

@router.post("/environments", response_model=EnvironmentOut, status_code=status.HTTP_201_CREATED)
async def create_env(body: EnvironmentIn, ctx: CtxDep, db: DbDep) -> EnvironmentOut:
    env = await svc.add_environment(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return EnvironmentOut.model_validate(env)


@router.patch("/environments/{env_id}", response_model=EnvironmentOut)
async def patch_env(
    env_id: str, body: EnvironmentUpdate, ctx: CtxDep, db: DbDep,
) -> EnvironmentOut:
    env = await svc.update_environment(db, ctx.project, env_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return EnvironmentOut.model_validate(env)


@router.delete("/environments/{env_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_env(env_id: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.delete_environment(db, ctx.project, env_id)
    await db.commit()


# ---------- infra (upsert-singleton) ----------

@router.patch("/infra", response_model=InfraOut)
async def patch_infra(body: InfraUpsert, ctx: CtxDep, db: DbDep) -> InfraOut:
    infra = await svc.upsert_infra(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return InfraOut.model_validate(infra)


# ---------- links ----------

@router.post("/links", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(body: LinkIn, ctx: CtxDep, db: DbDep) -> LinkOut:
    link = await svc.add_link(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return LinkOut.model_validate(link)


@router.patch("/links/{link_id}", response_model=LinkOut)
async def patch_link(link_id: str, body: LinkUpdate, ctx: CtxDep, db: DbDep) -> LinkOut:
    link = await svc.update_link(db, ctx.project, link_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return LinkOut.model_validate(link)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link_id: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.delete_link(db, ctx.project, link_id)
    await db.commit()


# ---------- commands ----------

@router.post("/commands", response_model=CommandOut, status_code=status.HTTP_201_CREATED)
async def create_command(body: CommandIn, ctx: CtxDep, db: DbDep) -> CommandOut:
    cmd = await svc.add_command(db, ctx.project, **body.model_dump(exclude_unset=True))
    await db.commit()
    return CommandOut.model_validate(cmd)


@router.patch("/commands/{cmd_id}", response_model=CommandOut)
async def patch_command(cmd_id: str, body: CommandUpdate, ctx: CtxDep, db: DbDep) -> CommandOut:
    cmd = await svc.update_command(db, ctx.project, cmd_id, **body.model_dump(exclude_unset=True))
    await db.commit()
    return CommandOut.model_validate(cmd)


@router.delete("/commands/{cmd_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_command(cmd_id: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.delete_command(db, ctx.project, cmd_id)
    await db.commit()


# ---------- stack ----------

@router.post("/stack", response_model=StackOut, status_code=status.HTTP_201_CREATED)
async def attach_stack(body: StackAttachIn, ctx: CtxDep, db: DbDep) -> StackOut:
    item, _ps = await svc.attach_stack(
        db, ctx.project, stack_item_slug=body.stack_item_slug, role=body.role,
    )
    await db.commit()
    return StackOut(stack_item_slug=item.slug, name=item.name, kind=item.kind, role=body.role)


@router.delete("/stack/{stack_item_slug}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_stack(stack_item_slug: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.detach_stack(db, ctx.project, stack_item_slug)
    await db.commit()


# ---------- tags ----------

@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def attach_tag(body: TagAttachIn, ctx: CtxDep, db: DbDep) -> TagOut:
    tag, _pt = await svc.attach_tag(
        db,
        ctx.project,
        workspace_id=ctx.workspace.id,
        tag_id=body.tag_id,
        name=body.name,
        color=body.color,
    )
    await db.commit()
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_tag(tag_id: str, ctx: CtxDep, db: DbDep) -> None:
    await svc.detach_tag(db, ctx.project, tag_id)
    await db.commit()
