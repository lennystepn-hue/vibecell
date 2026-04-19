from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import idea_svc

pytestmark = pytest.mark.integration


async def _make_ws(session: AsyncSession) -> Workspace:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    return ws


async def _make_project(session: AsyncSession, ws: Workspace) -> Project:
    project = Project(
        workspace_id=ws.id, slug=f"p-{new_ulid()[:6].lower()}", name="P"
    )
    session.add(project)
    await session.flush()
    return project


async def test_inbox_idea_and_triage(session: AsyncSession) -> None:
    ws = await _make_ws(session)
    idea = await idea_svc.create_idea(
        session, workspace_id=ws.id, body="Auto-pull stars", source="web",
    )
    assert idea.status == "inbox"
    assert idea.project_id is None
    project = await _make_project(session, ws)
    updated = await idea_svc.update_idea(
        session, workspace_id=ws.id, idea_id=idea.id, project_id=project.id,
    )
    assert updated.project_id == project.id
    assert updated.status == "triaged"


async def test_idea_reject_cross_workspace_project(session: AsyncSession) -> None:
    ws_a = await _make_ws(session)
    ws_b = await _make_ws(session)
    proj_b = await _make_project(session, ws_b)
    with pytest.raises(ValidationError):
        await idea_svc.create_idea(
            session, workspace_id=ws_a.id, body="x", project_id=proj_b.id,
        )


async def test_idea_workspace_isolation(session: AsyncSession) -> None:
    ws_a = await _make_ws(session)
    ws_b = await _make_ws(session)
    await idea_svc.create_idea(session, workspace_id=ws_a.id, body="a")
    await idea_svc.create_idea(session, workspace_id=ws_b.id, body="b")

    rows_a = await idea_svc.list_ideas(session, workspace_id=ws_a.id)
    rows_b = await idea_svc.list_ideas(session, workspace_id=ws_b.id)
    assert {r.body for r in rows_a} == {"a"}
    assert {r.body for r in rows_b} == {"b"}

    with pytest.raises(NotFoundError):
        # Trying to access ws_a's idea through ws_b should 404.
        await idea_svc.get_idea(session, workspace_id=ws_b.id, idea_id=rows_a[0].id)
