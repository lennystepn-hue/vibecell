"""Shared stack-items catalog + workspace tags."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.ulid import new_ulid
from app.models import StackItem, Tag


async def search_stack_items(
    db: AsyncSession,
    *,
    q: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[StackItem]:
    stmt = select(StackItem)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(StackItem.slug.ilike(pattern) | StackItem.name.ilike(pattern))
    if kind:
        stmt = stmt.where(StackItem.kind == kind)
    stmt = stmt.order_by(StackItem.slug.asc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def create_stack_item(
    db: AsyncSession,
    *,
    slug: str,
    name: str,
    kind: str | None = None,
    icon_url: str | None = None,
) -> StackItem:
    existing = (
        await db.execute(select(StackItem.id).where(StackItem.slug == slug))
    ).first()
    if existing is not None:
        raise ConflictError(detail=f"stack_item {slug!r} already exists")
    item = StackItem(id=new_ulid(), slug=slug, name=name, kind=kind, icon_url=icon_url)
    db.add(item)
    await db.flush()
    return item


async def list_tags(db: AsyncSession, *, workspace_id: str) -> list[Tag]:
    stmt = select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name.asc())
    return list((await db.execute(stmt)).scalars())


async def create_tag(
    db: AsyncSession,
    *,
    workspace_id: str,
    name: str,
    color: str | None = None,
) -> Tag:
    existing = (
        await db.execute(
            select(Tag.id).where(Tag.workspace_id == workspace_id, Tag.name == name)
        )
    ).first()
    if existing is not None:
        raise ConflictError(detail=f"tag {name!r} already exists in this workspace")
    tag = Tag(id=new_ulid(), workspace_id=workspace_id, name=name, color=color)
    db.add(tag)
    await db.flush()
    return tag
