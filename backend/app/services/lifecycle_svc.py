"""Lifecycle event CRUD.

Most lifecycle rows are written by other services (e.g., ship_svc
inserts kind='ship'). These helpers cover the rare manual-entry path.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import LifecycleEvent, Project


async def list_events(db: AsyncSession, *, project: Project) -> list[LifecycleEvent]:
    return list((await db.execute(
        select(LifecycleEvent)
        .where(LifecycleEvent.project_id == project.id)
        .order_by(LifecycleEvent.at.desc())
    )).scalars())


async def create_event(
    db: AsyncSession,
    *,
    project: Project,
    at: datetime,
    kind: str,
    detail: dict[str, Any] | None,
) -> LifecycleEvent:
    row = LifecycleEvent(
        id=new_ulid(),
        project_id=project.id,
        at=at,
        kind=kind,
        detail=detail,
    )
    db.add(row)
    await db.flush()
    return row
