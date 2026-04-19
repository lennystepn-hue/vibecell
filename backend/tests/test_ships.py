from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import LifecycleEvent, Project, User, Workspace, WorkspaceMember
from app.services import ship_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="shipproj", name="Sh")
    session.add(project)
    await session.flush()
    return project


async def test_create_ship_also_writes_lifecycle(session: AsyncSession) -> None:
    project = await _make_project(session)
    ship = await ship_svc.create_ship(
        session,
        project=project,
        shipped_at=datetime.now(UTC),
        version="v0.2.0",
        summary="Ship Loop backend",
        changelog_md="- endpoints\n- FTS",
    )
    assert ship.version == "v0.2.0"

    events = list((await session.execute(
        select(LifecycleEvent).where(LifecycleEvent.project_id == project.id)
    )).scalars())
    assert len(events) == 1
    assert events[0].kind == "ship"
    assert events[0].detail == {"ship_id": ship.id, "version": "v0.2.0"}


async def test_list_ships_newest_first(session: AsyncSession) -> None:
    project = await _make_project(session)
    await ship_svc.create_ship(session, project=project, version="v0.1")
    await ship_svc.create_ship(session, project=project, version="v0.2")
    rows = await ship_svc.list_ships(session, project=project)
    assert next(r.version for r in rows) == "v0.2"
