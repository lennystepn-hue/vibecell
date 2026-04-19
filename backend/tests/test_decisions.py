from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import decision_svc

pytestmark = pytest.mark.integration


async def _make_project(session: AsyncSession) -> Project:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(workspace_id=ws.id, slug="decproj", name="D")
    session.add(project)
    await session.flush()
    return project


async def test_create_and_list_decision(session: AsyncSession) -> None:
    project = await _make_project(session)
    d = await decision_svc.create_decision(
        session,
        project=project,
        title="Use Postgres",
        context="Considered SQLite",
        decision="Postgres for concurrent writes",
        consequences="Operationally heavier",
        reconsider_if="self-host adoption stalls",
    )
    assert d.id and d.title == "Use Postgres"
    rows = await decision_svc.list_decisions(session, project=project)
    assert [r.id for r in rows] == [d.id]


async def test_delete_decision(session: AsyncSession) -> None:
    project = await _make_project(session)
    d = await decision_svc.create_decision(
        session,
        project=project,
        title="ORM",
        context=None,
        decision="SQLAlchemy async",
        consequences=None,
        reconsider_if=None,
    )
    await decision_svc.delete_decision(session, project=project, decision_id=d.id)
    with pytest.raises(NotFoundError):
        await decision_svc.get_decision(session, project=project, decision_id=d.id)
