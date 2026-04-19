from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import note_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="nproj", name="N")
    session.add(project)
    await session.flush()
    return project


async def test_upsert_note_creates_and_replaces(session: AsyncSession) -> None:
    project = await _make_project(session)
    assert await note_svc.get_note(session, project=project) is None

    first = await note_svc.upsert_note(session, project=project, markdown="hello")
    assert first.markdown == "hello"

    second = await note_svc.upsert_note(session, project=project, markdown="world")
    assert second.markdown == "world"
    # Still a singleton row.
    same = await note_svc.get_note(session, project=project)
    assert same is not None and same.markdown == "world"
