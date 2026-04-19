"""Launch (PH/HN/X/etc.) CRUD."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Launch, Project


async def list_launches(db: AsyncSession, *, project: Project) -> list[Launch]:
    return list((await db.execute(
        select(Launch)
        .where(Launch.project_id == project.id)
        .order_by(Launch.launched_at.desc())
    )).scalars())


async def get_launch(
    db: AsyncSession, *, project: Project, launch_id: str
) -> Launch:
    row = (await db.execute(
        select(Launch).where(
            Launch.project_id == project.id, Launch.id == launch_id
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("launch", launch_id)
    return row


async def create_launch(
    db: AsyncSession,
    *,
    project: Project,
    platform: str,
    launched_at: datetime,
    url: str | None,
    metrics: dict[str, Any],
) -> Launch:
    row = Launch(
        id=new_ulid(),
        project_id=project.id,
        platform=platform,
        launched_at=launched_at,
        url=url,
        metrics=metrics,
    )
    db.add(row)
    await db.flush()
    return row


async def update_launch(
    db: AsyncSession,
    *,
    project: Project,
    launch_id: str,
    url: str | None = None,
    metrics: dict[str, Any] | None = None,
) -> Launch:
    row = await get_launch(db, project=project, launch_id=launch_id)
    if url is not None:
        row.url = url
    if metrics is not None:
        row.metrics = metrics
    await db.flush()
    return row
