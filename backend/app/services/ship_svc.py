"""Ship (release event) CRUD.

On create, atomically writes a `lifecycle_events` row with kind='ship' so
the lifecycle timeline includes ships without a separate client call.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import LifecycleEvent, Project, Ship


async def list_ships(db: AsyncSession, *, project: Project) -> list[Ship]:
    return list((await db.execute(
        select(Ship)
        .where(Ship.project_id == project.id)
        .order_by(Ship.shipped_at.desc())
    )).scalars())


async def create_ship(
    db: AsyncSession,
    *,
    project: Project,
    shipped_at: datetime | None = None,
    version: str | None = None,
    summary: str | None = None,
    changelog_md: str | None = None,
) -> Ship:
    when = shipped_at if shipped_at is not None else datetime.now(UTC)
    ship = Ship(
        id=new_ulid(),
        project_id=project.id,
        shipped_at=when,
        version=version,
        summary=summary,
        changelog_md=changelog_md,
    )
    db.add(ship)
    # Ensure the PK materialises before we reference it in the lifecycle row.
    await db.flush()

    lifecycle = LifecycleEvent(
        id=new_ulid(),
        project_id=project.id,
        at=when,
        kind="ship",
        detail={"ship_id": ship.id, "version": version},
    )
    db.add(lifecycle)
    await db.flush()

    # Fire-and-forget ship-shot capture: a screenshot of the live site right
    # now, attached to this ship_id. Runs in the background so the ship
    # response doesn't wait for chromium (~5s) to settle.
    from app.services import screenshot_svc  # defer to avoid import cycle
    screenshot_svc.schedule_background_capture(
        project_id=project.id, kind="ship", ship_id=ship.id,
    )

    # Live-event broadcast.
    from app.services import events as events_svc
    await events_svc.publish(project.id, "ship.created", {"ship_id": ship.id, "version": version})

    return ship
