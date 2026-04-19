"""Project groups CRUD + bulk reorder."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Project, ProjectGroup

_SLUG_RE = re.compile(r"[^a-z0-9-]")


def _slugify(name: str) -> str:
    s = _SLUG_RE.sub("-", name.lower()).strip("-")[:50]
    return s or "group"


async def list_groups(db: AsyncSession, *, workspace_id: str) -> list[ProjectGroup]:
    stmt = (
        select(ProjectGroup)
        .where(ProjectGroup.workspace_id == workspace_id)
        .order_by(ProjectGroup.position.asc())
    )
    return list((await db.execute(stmt)).scalars())


async def create_group(
    db: AsyncSession,
    *,
    workspace_id: str,
    name: str,
    slug: str | None = None,
    color: str | None = None,
) -> ProjectGroup:
    desired_slug = slug or _slugify(name)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,48}[a-z0-9]", desired_slug):
        raise ValidationError(detail=f"invalid group slug {desired_slug!r}")
    existing = (
        await db.execute(
            select(ProjectGroup.id).where(
                ProjectGroup.workspace_id == workspace_id,
                ProjectGroup.slug == desired_slug,
            )
        )
    ).first()
    if existing:
        raise ConflictError(detail=f"group slug {desired_slug!r} already exists")
    # position = max(existing) + 1
    max_pos = (
        await db.execute(
            select(ProjectGroup.position)
            .where(ProjectGroup.workspace_id == workspace_id)
            .order_by(ProjectGroup.position.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    group = ProjectGroup(
        id=new_ulid(),
        workspace_id=workspace_id,
        slug=desired_slug,
        name=name,
        color=color,
        position=(max_pos or 0) + 1,
    )
    db.add(group)
    await db.flush()
    return group


async def get_group(db: AsyncSession, *, workspace_id: str, group_id: str) -> ProjectGroup:
    group = (
        await db.execute(
            select(ProjectGroup).where(
                ProjectGroup.id == group_id,
                ProjectGroup.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if group is None:
        raise NotFoundError("group", group_id)
    return group


async def update_group(
    db: AsyncSession,
    *,
    group: ProjectGroup,
    name: str | None = None,
    color: str | None = None,
    position: int | None = None,
) -> ProjectGroup:
    if name is not None:
        group.name = name
    if color is not None:
        group.color = color
    if position is not None:
        group.position = position
    await db.flush()
    return group


async def delete_group(db: AsyncSession, *, group: ProjectGroup) -> None:
    await db.delete(group)
    await db.flush()


async def reorder_projects(
    db: AsyncSession,
    *,
    workspace_id: str,
    items: list[tuple[str, str | None, int]],
) -> int:
    """Batch update projects' group_id + position. `items` is [(slug, group_id, position), ...]."""
    count = 0
    for slug, group_id, position in items:
        project = (
            await db.execute(
                select(Project).where(
                    Project.workspace_id == workspace_id,
                    Project.slug == slug,
                )
            )
        ).scalar_one_or_none()
        if project is None:
            continue  # skip unknown slugs silently (caller sees the updated count)
        if group_id is not None:
            # verify group belongs to workspace
            g = (
                await db.execute(
                    select(ProjectGroup.id).where(
                        ProjectGroup.id == group_id,
                        ProjectGroup.workspace_id == workspace_id,
                    )
                )
            ).first()
            if g is None:
                continue
        project.group_id = group_id
        project.position = position
        count += 1
    await db.flush()
    return count
