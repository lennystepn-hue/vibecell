from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import (
    current_actor,
    current_workspace_id,
    install_audit_listener,
)
from app.core.ulid import new_ulid
from app.models import AuditLog, Project, User, Workspace

pytestmark = pytest.mark.integration


async def _bootstrap(session: AsyncSession) -> tuple[str, str, str]:
    user = User(email=f"audit-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    workspace = Workspace(slug=f"ws-{new_ulid()[:10]}", name="Audit WS", owner_id=user.id)
    session.add(workspace)
    await session.flush()
    return user.id, workspace.id, user.id


async def test_insert_emits_audit_row(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        project = Project(workspace_id=workspace_id, slug="audit-p", name="Audit P")
        session.add(project)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    rows = (await session.execute(
        select(AuditLog).where(AuditLog.entity == "projects")
    )).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.op == "create"
    assert row.entity_id == project.id
    assert row.actor == f"ui:{user_id}"
    assert row.workspace_id == workspace_id
    assert row.diff is not None
    assert row.diff.get("name") == [None, "Audit P"]


async def test_update_emits_audit_row_with_diff(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    project = Project(workspace_id=workspace_id, slug="u", name="Original")
    session.add(project)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        project.name = "Updated"
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    updates = (await session.execute(
        select(AuditLog).where(AuditLog.op == "update", AuditLog.entity == "projects")
    )).scalars().all()
    assert len(updates) == 1
    diff = updates[0].diff
    assert diff is not None
    assert diff.get("name") == ["Original", "Updated"]


async def test_delete_emits_audit_row(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    project = Project(workspace_id=workspace_id, slug="del", name="ToDelete")
    session.add(project)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        await session.delete(project)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    deletes = (await session.execute(
        select(AuditLog).where(AuditLog.op == "delete", AuditLog.entity == "projects")
    )).scalars().all()
    assert len(deletes) == 1


async def test_audit_log_itself_not_logged(session: AsyncSession) -> None:
    install_audit_listener()
    _user_id, workspace_id, _ = await _bootstrap(session)

    token_actor = current_actor.set("worker:test")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        manual = AuditLog(
            workspace_id=workspace_id, actor="worker:test", op="create",
            entity="stack_items", entity_id="01AAAA00000000000000000000",
            diff={"slug": [None, "foo"]},
        )
        session.add(manual)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    all_audit = (await session.execute(select(AuditLog))).scalars().all()
    # Only our manually-inserted row should exist; the listener must not
    # have recursively created another entry for the AuditLog insert.
    assert len(all_audit) == 1
