from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import Project, User, Workspace, WorkspaceMember
from app.services import decision_svc, idea_svc, note_svc, session_svc
from app.services import search as search_svc

pytestmark = pytest.mark.integration


async def _make_ws_project(session: AsyncSession) -> tuple[Workspace, Project]:
    user = User(email=f"u-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    ws = Workspace(slug=f"ws-{new_ulid()[:10]}", name="WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    project = Project(
        workspace_id=ws.id, slug="srchproj", name="Hangar Platform",
        pitch="centralised command centre for Postgres-backed indie apps",
    )
    session.add(project)
    await session.flush()
    return ws, project


async def test_search_hits_project_session_decision_idea_note(
    session: AsyncSession,
) -> None:
    ws, project = await _make_ws_project(session)

    await session_svc.create_session(
        session,
        project=project,
        started_at=datetime.now(UTC),
        ended_at=None,
        summary="Debugged Postgres replication lag",
        files_touched=[],
        commits=[],
        next_step="Upgrade to Postgres 16.2",
        source="manual",
    )
    await decision_svc.create_decision(
        session,
        project=project,
        title="Keep Postgres for v1",
        context="considered SQLite edge-first",
        decision="Postgres centralised; simpler for MVP",
        consequences="ops overhead",
        reconsider_if="MRR > 100k",
    )
    await idea_svc.create_idea(
        session, workspace_id=ws.id, body="auto-pull GitHub stars into Postgres",
        source="web",
    )
    await note_svc.upsert_note(
        session, project=project, markdown="## Postgres playbook\nvacuum weekly",
    )

    hits = await search_svc.union_search(
        session, workspace_id=ws.id, query="Postgres", limit=50,
    )
    entities = {h.entity for h in hits}
    assert {"project", "session", "decision", "idea", "note"}.issubset(entities)
    # Every hit points back to the workspace we created.
    for h in hits:
        if h.entity == "idea" or h.entity == "project":
            continue
        assert h.project_slug == project.slug


async def test_search_entity_filter_narrows(session: AsyncSession) -> None:
    ws, project = await _make_ws_project(session)
    await decision_svc.create_decision(
        session,
        project=project,
        title="Use async SQLAlchemy",
        context=None,
        decision="AsyncSession throughout",
        consequences=None,
        reconsider_if=None,
    )
    await idea_svc.create_idea(
        session, workspace_id=ws.id, body="SQLAlchemy autogen migrations", source="web",
    )

    only_decisions = await search_svc.union_search(
        session, workspace_id=ws.id, query="SQLAlchemy",
        entity_filter="decision",
    )
    assert {h.entity for h in only_decisions} == {"decision"}
