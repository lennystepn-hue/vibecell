from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import launch_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="lproj", name="L")
    session.add(project)
    await session.flush()
    return project


async def test_create_and_update_launch_metrics(session: AsyncSession) -> None:
    project = await _make_project(session)
    launch = await launch_svc.create_launch(
        session,
        project=project,
        platform="ph",
        launched_at=datetime.now(UTC),
        url="https://www.producthunt.com/posts/hangar",
        metrics={"upvotes": 42},
    )
    updated = await launch_svc.update_launch(
        session,
        project=project,
        launch_id=launch.id,
        metrics={"upvotes": 210, "comments": 18},
    )
    assert updated.metrics == {"upvotes": 210, "comments": 18}


async def test_list_launches_newest_first(session: AsyncSession) -> None:
    project = await _make_project(session)
    await launch_svc.create_launch(
        session, project=project, platform="hn",
        launched_at=datetime(2026, 1, 1, tzinfo=UTC),
        url=None, metrics={},
    )
    await launch_svc.create_launch(
        session, project=project, platform="x",
        launched_at=datetime(2026, 2, 1, tzinfo=UTC),
        url=None, metrics={},
    )
    rows = await launch_svc.list_launches(session, project=project)
    assert [r.platform for r in rows] == ["x", "hn"]
