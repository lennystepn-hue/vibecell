# Phase 6 — Project Children

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** All 8 sub-resources on a project: context, repos, environments, infra, links, commands, stack, tags. Plus update `GET /projects/:slug` to return the full aggregate (children included).

**Prerequisite:** Phase 5 complete (HEAD ≥ `7f8f4fd`).

---

## Endpoints (24 total)

```
# Context (singleton — PK is project_id)
GET    /api/v1/projects/:slug/context
PATCH  /api/v1/projects/:slug/context

# Repos (0..n)
POST   /api/v1/projects/:slug/repos
PATCH  /api/v1/projects/:slug/repos/:id
DELETE /api/v1/projects/:slug/repos/:id

# Environments (0..n)
POST   /api/v1/projects/:slug/environments
PATCH  /api/v1/projects/:slug/environments/:id
DELETE /api/v1/projects/:slug/environments/:id

# Infra (singleton — PK is project_id; PATCH upserts)
PATCH  /api/v1/projects/:slug/infra

# Links (0..n)
POST   /api/v1/projects/:slug/links
PATCH  /api/v1/projects/:slug/links/:id
DELETE /api/v1/projects/:slug/links/:id

# Commands (0..n)
POST   /api/v1/projects/:slug/commands
PATCH  /api/v1/projects/:slug/commands/:id
DELETE /api/v1/projects/:slug/commands/:id

# Stack (composite PK: project_id + stack_item_slug)
POST   /api/v1/projects/:slug/stack        body: { stack_item_slug, role? }
DELETE /api/v1/projects/:slug/stack/:stack_item_slug

# Tags (composite PK: project_id + tag_id)
POST   /api/v1/projects/:slug/tags         body: { tag_id } OR { name, color? } (attach or create+attach)
DELETE /api/v1/projects/:slug/tags/:tag_id
```

Plus refactor: `GET /api/v1/projects/:slug` now returns `ProjectFullOut` with all children nested.

---

## Files

```
backend/app/
├── api/v1/
│   └── project_children.py          one router mounted on /api/v1/projects/{slug}/...
├── api/v1/projects.py               (modify) GET returns ProjectFullOut
├── schemas/project.py               (modify) add ProjectFullOut + child I/O schemas
├── services/project_children.py     CRUD helpers for each sub-resource
└── (no model changes)
tests/
├── test_project_context.py
├── test_project_repos.py
├── test_project_environments.py
├── test_project_infra.py
├── test_project_links.py
├── test_project_commands.py
├── test_project_stack.py
├── test_project_tags.py
└── test_project_full_aggregate.py   GET /projects/:slug with nested children
```

---

## Task 6.1 — Schemas

Add to `backend/app/schemas/project.py` at the bottom:

```python
# --- Child sub-resource schemas ---


class RepoIn(BaseModel):
    role: str | None = Field(default=None, max_length=20)
    git_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, max_length=100)
    local_path: str | None = Field(default=None, max_length=500)
    primary_lang: str | None = Field(default=None, max_length=50)
    license: str | None = Field(default=None, max_length=50)


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str | None = None
    git_url: str | None = None
    default_branch: str | None = None
    local_path: str | None = None
    primary_lang: str | None = None
    license: str | None = None


class EnvironmentIn(BaseModel):
    kind: str = Field(..., pattern=r"^(local|preview|staging|prod)$")
    url: str | None = Field(default=None, max_length=500)
    env_template_path: str | None = Field(default=None, max_length=500)
    db_alias: str | None = Field(default=None, max_length=100)


class EnvironmentUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(local|preview|staging|prod)$")
    url: str | None = Field(default=None, max_length=500)
    env_template_path: str | None = Field(default=None, max_length=500)
    db_alias: str | None = Field(default=None, max_length=100)


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    url: str | None = None
    env_template_path: str | None = None
    db_alias: str | None = None


class InfraUpsert(BaseModel):
    server_alias: str | None = Field(default=None, max_length=100)
    domain_primary: str | None = Field(default=None, max_length=255)
    domains: list[str] | None = None
    dns_provider: str | None = Field(default=None, max_length=50)
    db_host: str | None = Field(default=None, max_length=255)
    cdn: str | None = Field(default=None, max_length=50)
    object_storage: str | None = Field(default=None, max_length=255)


class InfraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_alias: str | None = None
    domain_primary: str | None = None
    domains: list[str] = []
    dns_provider: str | None = None
    db_host: str | None = None
    cdn: str | None = None
    object_storage: str | None = None


class ContextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list = []
    known_issues: list = []
    blocked_by: str | None = None


class ContextUpsert(BaseModel):
    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list | None = None
    known_issues: list | None = None
    blocked_by: str | None = None


class LinkIn(BaseModel):
    kind: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    url: str = Field(..., min_length=1, max_length=1000)


class LinkUpdate(BaseModel):
    kind: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=1000)


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str | None = None
    label: str | None = None
    url: str


class CommandIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    command: str = Field(..., min_length=1, max_length=2000)
    run_in: str = Field(default="terminal", pattern=r"^(terminal|background)$")
    confirm_required: int = 1


class CommandUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    command: str | None = Field(default=None, min_length=1, max_length=2000)
    run_in: str | None = Field(default=None, pattern=r"^(terminal|background)$")
    confirm_required: int | None = None


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    command: str
    run_in: str
    confirm_required: int


class StackAttachIn(BaseModel):
    stack_item_slug: str = Field(..., min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=20)


class StackOut(BaseModel):
    stack_item_slug: str
    name: str
    kind: str | None = None
    role: str | None = None


class TagAttachIn(BaseModel):
    tag_id: str | None = None
    name: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=20)


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str | None = None


class ProjectFullOut(ProjectOut):
    """Project detail + nested children. Used by GET /projects/:slug."""

    context: ContextOut | None = None
    infra: InfraOut | None = None
    repos: list[RepoOut] = []
    environments: list[EnvironmentOut] = []
    links: list[LinkOut] = []
    commands: list[CommandOut] = []
    stack: list[StackOut] = []
    tags: list[TagOut] = []
```

Commit: `feat(backend): schemas for project children (context/repos/envs/infra/links/commands/stack/tags) + ProjectFullOut`

---

## Task 6.2 — Services

**File:** `backend/app/services/project_children.py`

```python
"""CRUD helpers for project sub-resources."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import (
    Project,
    ProjectCommand,
    ProjectContext,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
    ProjectRepo,
    ProjectStack,
    ProjectTag,
    StackItem,
    Tag,
)


# ---------- context ----------

async def get_context(db: AsyncSession, project: Project) -> ProjectContext | None:
    return (await db.execute(
        select(ProjectContext).where(ProjectContext.project_id == project.id)
    )).scalar_one_or_none()


async def upsert_context(
    db: AsyncSession,
    project: Project,
    **fields,
) -> ProjectContext:
    ctx = await get_context(db, project)
    if ctx is None:
        ctx = ProjectContext(project_id=project.id)
        db.add(ctx)
    for key, value in fields.items():
        if value is not None:
            setattr(ctx, key, value)
    await db.flush()
    return ctx


# ---------- repos ----------

async def add_repo(db: AsyncSession, project: Project, **fields) -> ProjectRepo:
    repo = ProjectRepo(id=new_ulid(), project_id=project.id, **{k: v for k, v in fields.items() if v is not None})
    db.add(repo)
    await db.flush()
    return repo


async def get_repo(db: AsyncSession, project: Project, repo_id: str) -> ProjectRepo:
    repo = (await db.execute(
        select(ProjectRepo).where(
            ProjectRepo.project_id == project.id, ProjectRepo.id == repo_id
        )
    )).scalar_one_or_none()
    if repo is None:
        raise NotFoundError("repo", repo_id)
    return repo


async def update_repo(db: AsyncSession, project: Project, repo_id: str, **fields) -> ProjectRepo:
    repo = await get_repo(db, project, repo_id)
    for key, value in fields.items():
        if value is not None:
            setattr(repo, key, value)
    await db.flush()
    return repo


async def delete_repo(db: AsyncSession, project: Project, repo_id: str) -> None:
    repo = await get_repo(db, project, repo_id)
    await db.delete(repo)
    await db.flush()


async def list_repos(db: AsyncSession, project: Project) -> list[ProjectRepo]:
    return list((await db.execute(
        select(ProjectRepo).where(ProjectRepo.project_id == project.id).order_by(ProjectRepo.id.asc())
    )).scalars())


# ---------- environments ----------

async def add_environment(db: AsyncSession, project: Project, **fields) -> ProjectEnvironment:
    env = ProjectEnvironment(id=new_ulid(), project_id=project.id, **{k: v for k, v in fields.items() if v is not None})
    db.add(env)
    await db.flush()
    return env


async def get_environment(db: AsyncSession, project: Project, env_id: str) -> ProjectEnvironment:
    env = (await db.execute(
        select(ProjectEnvironment).where(
            ProjectEnvironment.project_id == project.id, ProjectEnvironment.id == env_id
        )
    )).scalar_one_or_none()
    if env is None:
        raise NotFoundError("environment", env_id)
    return env


async def update_environment(db: AsyncSession, project: Project, env_id: str, **fields) -> ProjectEnvironment:
    env = await get_environment(db, project, env_id)
    for key, value in fields.items():
        if value is not None:
            setattr(env, key, value)
    await db.flush()
    return env


async def delete_environment(db: AsyncSession, project: Project, env_id: str) -> None:
    env = await get_environment(db, project, env_id)
    await db.delete(env)
    await db.flush()


async def list_environments(db: AsyncSession, project: Project) -> list[ProjectEnvironment]:
    return list((await db.execute(
        select(ProjectEnvironment).where(ProjectEnvironment.project_id == project.id).order_by(ProjectEnvironment.kind.asc())
    )).scalars())


# ---------- infra ----------

async def get_infra(db: AsyncSession, project: Project) -> ProjectInfra | None:
    return (await db.execute(
        select(ProjectInfra).where(ProjectInfra.project_id == project.id)
    )).scalar_one_or_none()


async def upsert_infra(db: AsyncSession, project: Project, **fields) -> ProjectInfra:
    infra = await get_infra(db, project)
    if infra is None:
        infra = ProjectInfra(project_id=project.id)
        db.add(infra)
    for key, value in fields.items():
        if value is not None:
            setattr(infra, key, value)
    await db.flush()
    return infra


# ---------- links ----------

async def add_link(db: AsyncSession, project: Project, **fields) -> ProjectLink:
    link = ProjectLink(id=new_ulid(), project_id=project.id, **{k: v for k, v in fields.items() if v is not None})
    db.add(link)
    await db.flush()
    return link


async def get_link(db: AsyncSession, project: Project, link_id: str) -> ProjectLink:
    link = (await db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id == project.id, ProjectLink.id == link_id
        )
    )).scalar_one_or_none()
    if link is None:
        raise NotFoundError("link", link_id)
    return link


async def update_link(db: AsyncSession, project: Project, link_id: str, **fields) -> ProjectLink:
    link = await get_link(db, project, link_id)
    for key, value in fields.items():
        if value is not None:
            setattr(link, key, value)
    await db.flush()
    return link


async def delete_link(db: AsyncSession, project: Project, link_id: str) -> None:
    link = await get_link(db, project, link_id)
    await db.delete(link)
    await db.flush()


async def list_links(db: AsyncSession, project: Project) -> list[ProjectLink]:
    return list((await db.execute(
        select(ProjectLink).where(ProjectLink.project_id == project.id).order_by(ProjectLink.id.asc())
    )).scalars())


# ---------- commands ----------

async def add_command(db: AsyncSession, project: Project, **fields) -> ProjectCommand:
    cmd = ProjectCommand(id=new_ulid(), project_id=project.id, **{k: v for k, v in fields.items() if v is not None})
    db.add(cmd)
    await db.flush()
    return cmd


async def get_command(db: AsyncSession, project: Project, cmd_id: str) -> ProjectCommand:
    cmd = (await db.execute(
        select(ProjectCommand).where(
            ProjectCommand.project_id == project.id, ProjectCommand.id == cmd_id
        )
    )).scalar_one_or_none()
    if cmd is None:
        raise NotFoundError("command", cmd_id)
    return cmd


async def update_command(db: AsyncSession, project: Project, cmd_id: str, **fields) -> ProjectCommand:
    cmd = await get_command(db, project, cmd_id)
    for key, value in fields.items():
        if value is not None:
            setattr(cmd, key, value)
    await db.flush()
    return cmd


async def delete_command(db: AsyncSession, project: Project, cmd_id: str) -> None:
    cmd = await get_command(db, project, cmd_id)
    await db.delete(cmd)
    await db.flush()


async def list_commands(db: AsyncSession, project: Project) -> list[ProjectCommand]:
    return list((await db.execute(
        select(ProjectCommand).where(ProjectCommand.project_id == project.id).order_by(ProjectCommand.id.asc())
    )).scalars())


# ---------- stack ----------

async def attach_stack(
    db: AsyncSession, project: Project, *, stack_item_slug: str, role: str | None,
) -> tuple[StackItem, ProjectStack]:
    item = (await db.execute(
        select(StackItem).where(StackItem.slug == stack_item_slug)
    )).scalar_one_or_none()
    if item is None:
        raise NotFoundError("stack_item", stack_item_slug)

    existing = (await db.execute(
        select(ProjectStack).where(
            ProjectStack.project_id == project.id,
            ProjectStack.stack_item_id == item.id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(detail=f"stack_item {stack_item_slug!r} already attached")

    ps = ProjectStack(project_id=project.id, stack_item_id=item.id, role=role)
    db.add(ps)
    await db.flush()
    return item, ps


async def detach_stack(db: AsyncSession, project: Project, stack_item_slug: str) -> None:
    item = (await db.execute(
        select(StackItem).where(StackItem.slug == stack_item_slug)
    )).scalar_one_or_none()
    if item is None:
        raise NotFoundError("stack_item", stack_item_slug)
    result = await db.execute(
        delete(ProjectStack).where(
            ProjectStack.project_id == project.id,
            ProjectStack.stack_item_id == item.id,
        )
    )
    await db.flush()
    if result.rowcount == 0:
        raise NotFoundError("stack attachment", stack_item_slug)


async def list_stack(db: AsyncSession, project: Project) -> list[tuple[StackItem, ProjectStack]]:
    rows = (await db.execute(
        select(StackItem, ProjectStack)
        .join(ProjectStack, ProjectStack.stack_item_id == StackItem.id)
        .where(ProjectStack.project_id == project.id)
        .order_by(StackItem.slug.asc())
    )).all()
    return [(si, ps) for si, ps in rows]


# ---------- tags ----------

async def attach_tag(
    db: AsyncSession,
    project: Project,
    *,
    workspace_id: str,
    tag_id: str | None = None,
    name: str | None = None,
    color: str | None = None,
) -> tuple[Tag, ProjectTag]:
    if tag_id is None and name is None:
        raise ValidationError(detail="tag_id or name required")

    if tag_id is not None:
        tag = (await db.execute(
            select(Tag).where(Tag.id == tag_id, Tag.workspace_id == workspace_id)
        )).scalar_one_or_none()
        if tag is None:
            raise NotFoundError("tag", tag_id)
    else:
        assert name is not None
        tag = (await db.execute(
            select(Tag).where(Tag.workspace_id == workspace_id, Tag.name == name)
        )).scalar_one_or_none()
        if tag is None:
            tag = Tag(id=new_ulid(), workspace_id=workspace_id, name=name, color=color)
            db.add(tag)
            await db.flush()

    existing = (await db.execute(
        select(ProjectTag).where(
            ProjectTag.project_id == project.id,
            ProjectTag.tag_id == tag.id,
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise ConflictError(detail=f"tag {tag.name!r} already attached")

    pt = ProjectTag(project_id=project.id, tag_id=tag.id)
    db.add(pt)
    await db.flush()
    return tag, pt


async def detach_tag(db: AsyncSession, project: Project, tag_id: str) -> None:
    result = await db.execute(
        delete(ProjectTag).where(
            ProjectTag.project_id == project.id,
            ProjectTag.tag_id == tag_id,
        )
    )
    await db.flush()
    if result.rowcount == 0:
        raise NotFoundError("tag attachment", tag_id)


async def list_tags(db: AsyncSession, project: Project) -> list[Tag]:
    rows = (await db.execute(
        select(Tag)
        .join(ProjectTag, ProjectTag.tag_id == Tag.id)
        .where(ProjectTag.project_id == project.id)
        .order_by(Tag.name.asc())
    )).scalars()
    return list(rows)
```

Commit: `feat(backend): project_children service — CRUD for all 8 sub-resource types`

---

## Task 6.3 — Router (24 endpoints in one module)

**File:** `backend/app/api/v1/project_children.py`

```python
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
```

Wire in `main.py`:
```python
from app.api.v1.project_children import router as project_children_router
# ...
app.include_router(project_children_router)
```

Commit: `feat(backend): project_children router — 24 endpoints (context/repos/envs/infra/links/commands/stack/tags)`

---

## Task 6.4 — Refactor GET /projects/:slug → full aggregate

Replace the `get` route in `backend/app/api/v1/projects.py`:

```python
from app.schemas.project import ProjectFullOut
from app.services import project_children as children_svc
# ... existing imports unchanged


@router.get("/{slug}", response_model=ProjectFullOut)
async def get(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectFullOut:
    from app.schemas.project import (
        CommandOut,
        ContextOut,
        EnvironmentOut,
        InfraOut,
        LinkOut,
        RepoOut,
        StackOut,
        TagOut,
    )

    ctx_row = await children_svc.get_context(db, ctx.project)
    infra_row = await children_svc.get_infra(db, ctx.project)
    repos = await children_svc.list_repos(db, ctx.project)
    envs = await children_svc.list_environments(db, ctx.project)
    links = await children_svc.list_links(db, ctx.project)
    commands = await children_svc.list_commands(db, ctx.project)
    stack = await children_svc.list_stack(db, ctx.project)
    tags = await children_svc.list_tags(db, ctx.project)

    base = _to_out(ctx.project)
    return ProjectFullOut(
        **base.model_dump(),
        context=ContextOut.model_validate(ctx_row) if ctx_row else None,
        infra=InfraOut.model_validate(infra_row) if infra_row else None,
        repos=[RepoOut.model_validate(r) for r in repos],
        environments=[EnvironmentOut.model_validate(e) for e in envs],
        links=[LinkOut.model_validate(link) for link in links],
        commands=[CommandOut.model_validate(c) for c in commands],
        stack=[
            StackOut(stack_item_slug=si.slug, name=si.name, kind=si.kind, role=ps.role)
            for si, ps in stack
        ],
        tags=[TagOut.model_validate(t) for t in tags],
    )
```

Commit: `refactor(backend): GET /projects/:slug returns full aggregate (children nested)`

---

## Task 6.5 — Tests (9 files)

Each follows the same auth-helper pattern. One test per file demonstrating happy path; plus a 404 where applicable. Keep tight — ~3-5 tests per file.

### `backend/tests/test_project_context.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_context_get_returns_empty_before_upsert(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-empty@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            resp = await c.get("/api/v1/projects/p/context")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_focus"] is None
    assert body["open_questions"] == []


async def test_context_patch_upserts(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-patch@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            resp = await c.patch(
                "/api/v1/projects/p/context",
                json={
                    "current_focus": "Ship webhook",
                    "next_step": "Handle deletion",
                    "open_questions": ["Pro-rata?"],
                },
            )
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["current_focus"] == "Ship webhook"
    assert body["open_questions"] == ["Pro-rata?"]


async def test_context_404_when_project_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "ctx-404@example.com")
            resp = await c.get("/api/v1/projects/nope/context")
    finally:
        clear_db_override()
    assert resp.status_code == 404
```

### `backend/tests/test_project_repos.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_repo_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "repos@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_create = await c.post(
                "/api/v1/projects/p/repos",
                json={"role": "monorepo", "git_url": "git@github.com:x/y.git", "primary_lang": "Python"},
            )
            assert r_create.status_code == 201
            repo_id = r_create.json()["id"]

            r_patch = await c.patch(
                f"/api/v1/projects/p/repos/{repo_id}",
                json={"default_branch": "main"},
            )
            assert r_patch.status_code == 200
            assert r_patch.json()["default_branch"] == "main"

            r_del = await c.delete(f"/api/v1/projects/p/repos/{repo_id}")
            assert r_del.status_code == 204

            r_del2 = await c.delete(f"/api/v1/projects/p/repos/{repo_id}")
            assert r_del2.status_code == 404
    finally:
        clear_db_override()
```

### `backend/tests/test_project_environments.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_environment_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "envs@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r = await c.post(
                "/api/v1/projects/p/environments",
                json={"kind": "prod", "url": "https://x.com"},
            )
            assert r.status_code == 201
            env_id = r.json()["id"]
            r_patch = await c.patch(
                f"/api/v1/projects/p/environments/{env_id}",
                json={"url": "https://y.com"},
            )
            assert r_patch.status_code == 200
            assert r_patch.json()["url"] == "https://y.com"
            r_del = await c.delete(f"/api/v1/projects/p/environments/{env_id}")
            assert r_del.status_code == 204
    finally:
        clear_db_override()


async def test_environment_rejects_invalid_kind(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "envs-bad@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r = await c.post(
                "/api/v1/projects/p/environments", json={"kind": "nope"},
            )
    finally:
        clear_db_override()
    assert r.status_code == 422
```

### `backend/tests/test_project_infra.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_infra_upsert(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "infra@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r1 = await c.patch(
                "/api/v1/projects/p/infra",
                json={"server_alias": "prod", "domain_primary": "example.com"},
            )
            assert r1.status_code == 200
            assert r1.json()["server_alias"] == "prod"

            # Second patch updates only domains
            r2 = await c.patch(
                "/api/v1/projects/p/infra",
                json={"domains": ["example.com", "example.io"]},
            )
    finally:
        clear_db_override()
    assert r2.status_code == 200
    body = r2.json()
    assert body["server_alias"] == "prod"  # preserved
    assert body["domains"] == ["example.com", "example.io"]
```

### `backend/tests/test_project_links.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_link_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "links@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_c = await c.post(
                "/api/v1/projects/p/links",
                json={"kind": "live", "label": "Production", "url": "https://x.com"},
            )
            assert r_c.status_code == 201
            lid = r_c.json()["id"]
            r_u = await c.patch(
                f"/api/v1/projects/p/links/{lid}",
                json={"label": "Updated"},
            )
            assert r_u.status_code == 200
            r_d = await c.delete(f"/api/v1/projects/p/links/{lid}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
```

### `backend/tests/test_project_commands.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_command_crud(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "cmds@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_c = await c.post(
                "/api/v1/projects/p/commands",
                json={"label": "Deploy", "command": "make deploy"},
            )
            assert r_c.status_code == 201
            cid = r_c.json()["id"]
            r_u = await c.patch(
                f"/api/v1/projects/p/commands/{cid}",
                json={"run_in": "background"},
            )
            assert r_u.status_code == 200
            assert r_u.json()["run_in"] == "background"
            r_d = await c.delete(f"/api/v1/projects/p/commands/{cid}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
```

### `backend/tests/test_project_stack.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_attach_and_detach_stack(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/p/stack",
                json={"stack_item_slug": "fastapi", "role": "primary"},
            )
            assert r_a.status_code == 201
            assert r_a.json()["stack_item_slug"] == "fastapi"

            r_dup = await c.post(
                "/api/v1/projects/p/stack",
                json={"stack_item_slug": "fastapi"},
            )
            assert r_dup.status_code == 409

            r_d = await c.delete("/api/v1/projects/p/stack/fastapi")
    finally:
        clear_db_override()
    assert r_d.status_code == 204


async def test_stack_404_for_unknown_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-404@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r = await c.post(
                "/api/v1/projects/p/stack", json={"stack_item_slug": "nonexistent"},
            )
    finally:
        clear_db_override()
    assert r.status_code == 404
```

### `backend/tests/test_project_tags.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_attach_tag_by_name_creates_tag(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/p/tags",
                json={"name": "backend", "color": "#8ab4ff"},
            )
    finally:
        clear_db_override()
    assert r_a.status_code == 201
    body = r_a.json()
    assert body["name"] == "backend"
    assert body["color"] == "#8ab4ff"


async def test_detach_tag_by_id(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-del@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            r_a = await c.post(
                "/api/v1/projects/p/tags", json={"name": "frontend"},
            )
            tag_id = r_a.json()["id"]
            r_d = await c.delete(f"/api/v1/projects/p/tags/{tag_id}")
    finally:
        clear_db_override()
    assert r_d.status_code == 204
```

### `backend/tests/test_project_full_aggregate.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_project_returns_full_aggregate(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "agg@example.com")
            await c.post("/api/v1/projects", json={"slug": "p", "name": "P"})
            await c.patch(
                "/api/v1/projects/p/context",
                json={"current_focus": "focus"},
            )
            await c.post(
                "/api/v1/projects/p/repos",
                json={"git_url": "git@example.com:x.git"},
            )
            await c.post(
                "/api/v1/projects/p/stack",
                json={"stack_item_slug": "fastapi"},
            )
            await c.post(
                "/api/v1/projects/p/tags",
                json={"name": "python"},
            )
            resp = await c.get("/api/v1/projects/p")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert body["context"]["current_focus"] == "focus"
    assert len(body["repos"]) == 1
    assert body["repos"][0]["git_url"] == "git@example.com:x.git"
    assert len(body["stack"]) == 1
    assert body["stack"][0]["stack_item_slug"] == "fastapi"
    assert len(body["tags"]) == 1
    assert body["tags"][0]["name"] == "python"
```

Commit: `test(backend): project children route tests (9 files, 8 sub-resources + full aggregate)`

---

## Phase 6 complete when

- [ ] 24 sub-resource endpoints respond correctly.
- [ ] `GET /projects/:slug` returns nested children.
- [ ] `ruff check .` + `mypy app tests` green.
- [ ] All tests pass (~95+ after Phase 6: 82 prior + ~14 new).
- [ ] 5 commits on main (6.1–6.5).
- [ ] Staging test run green.
