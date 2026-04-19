"""CRUD helpers for project sub-resources."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import CursorResult, delete, select
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
    **fields: Any,
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

async def add_repo(db: AsyncSession, project: Project, **fields: Any) -> ProjectRepo:
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


async def update_repo(db: AsyncSession, project: Project, repo_id: str, **fields: Any) -> ProjectRepo:
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

async def add_environment(db: AsyncSession, project: Project, **fields: Any) -> ProjectEnvironment:
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


async def update_environment(db: AsyncSession, project: Project, env_id: str, **fields: Any) -> ProjectEnvironment:
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


async def upsert_infra(db: AsyncSession, project: Project, **fields: Any) -> ProjectInfra:
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

async def add_link(db: AsyncSession, project: Project, **fields: Any) -> ProjectLink:
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


async def update_link(db: AsyncSession, project: Project, link_id: str, **fields: Any) -> ProjectLink:
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

async def add_command(db: AsyncSession, project: Project, **fields: Any) -> ProjectCommand:
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


async def update_command(db: AsyncSession, project: Project, cmd_id: str, **fields: Any) -> ProjectCommand:
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
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            delete(ProjectStack).where(
                ProjectStack.project_id == project.id,
                ProjectStack.stack_item_id == item.id,
            )
        ),
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
    result = cast(
        "CursorResult[Any]",
        await db.execute(
            delete(ProjectTag).where(
                ProjectTag.project_id == project.id,
                ProjectTag.tag_id == tag_id,
            )
        ),
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
