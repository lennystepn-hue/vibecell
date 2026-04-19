from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import lifecycle_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="lcproj", name="Lc")
    session.add(project)
    await session.flush()
    return project


async def test_create_and_list_event(session: AsyncSession) -> None:
    project = await _make_project(session)
    ev = await lifecycle_svc.create_event(
        session,
        project=project,
        at=datetime.now(UTC),
        kind="first_user",
        detail={"source": "twitter"},
    )
    assert ev.kind == "first_user"
    rows = await lifecycle_svc.list_events(session, project=project)
    assert len(rows) == 1
