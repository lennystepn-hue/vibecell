from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import session_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="sessproj", name="S")
    session.add(project)
    await session.flush()
    return project


async def test_create_and_list_session(session: AsyncSession) -> None:
    project = await _make_project(session)
    started = datetime.now(UTC) - timedelta(hours=1)
    s = await session_svc.create_session(
        session,
        project=project,
        started_at=started,
        ended_at=None,
        summary="built the thing",
        files_touched=["app/main.py"],
        commits=[],
        next_step="write tests",
        source="skill",
    )
    assert s.id
    assert len(s.id) == 26
    assert s.project_id == project.id

    items, cursor = await session_svc.list_sessions(session, project=project)
    assert len(items) == 1
    assert items[0].summary == "built the thing"
    assert cursor is None


async def test_update_session_patches_fields(session: AsyncSession) -> None:
    project = await _make_project(session)
    s = await session_svc.create_session(
        session,
        project=project,
        started_at=datetime.now(UTC),
        ended_at=None,
        summary=None,
        files_touched=[],
        commits=[],
        next_step=None,
        source="manual",
    )
    later = datetime.now(UTC)
    updated = await session_svc.update_session(
        session, project=project, session_id=s.id,
        ended_at=later, summary="done",
    )
    assert updated.ended_at == later
    assert updated.summary == "done"


async def test_session_404_wrong_id(session: AsyncSession) -> None:
    project = await _make_project(session)
    with pytest.raises(NotFoundError):
        await session_svc.get_session(session, project=project, session_id="bogus")
