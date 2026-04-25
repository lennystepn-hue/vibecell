"""Spec-6 Sprint A3: GDPR data-export + account-delete.

Cover:
  - export gathers user + workspace + projects
  - purge wipes everything for a solo user
  - purge refused if user owns a workspace with co-members
  - purge cascades through project_* tables
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.ulid import new_ulid
from app.models import (
    Project,
    User,
    Workspace,
    WorkspaceKey,
    WorkspaceMember,
)
from app.services import account_purge
from app.services.login import issue_magic_link, verify_magic_link

pytestmark = pytest.mark.integration


async def _signup(session: AsyncSession, email: str) -> User:
    raw = await issue_magic_link(session, email=email)
    await session.commit()
    await verify_magic_link(session, raw_token=raw)
    await session.commit()
    return (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one()


async def _add_member(
    session: AsyncSession, *, workspace_id: str, user_id: str, role: str = "member"
) -> None:
    session.add(WorkspaceMember(workspace_id=workspace_id, user_id=user_id, role=role))
    await session.flush()


async def test_export_includes_user_and_workspace(session: AsyncSession) -> None:
    user = await _signup(session, "export-a3@example.com")

    payload = await account_purge.gather_user_data(session, user.id)

    assert payload["user"]["email"] == "export-a3@example.com"
    assert len(payload["workspaces"]) == 1
    assert any(
        m["user_id"] == user.id for m in payload["workspace_members"]
    )


async def test_export_includes_projects(session: AsyncSession) -> None:
    user = await _signup(session, "export-projects-a3@example.com")
    ws = (
        await session.execute(
            select(Workspace).where(Workspace.owner_id == user.id)
        )
    ).scalar_one()

    proj = Project(
        id=new_ulid(),
        workspace_id=ws.id,
        slug="export-test",
        name="Export Test",
        pitch="Should appear in export",
        status="building",
        emoji="📦",
    )
    session.add(proj)
    await session.flush()

    payload = await account_purge.gather_user_data(session, user.id)

    assert any(p["slug"] == "export-test" for p in payload["projects"])


async def test_purge_wipes_solo_user(session: AsyncSession) -> None:
    user = await _signup(session, "purge-solo-a3@example.com")
    user_id = user.id

    await account_purge.purge(session, user_id)
    await session.commit()

    # User row gone
    gone = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    assert gone is None

    # Workspace gone too (owner_id == user_id, sole-member, cascade-deleted via service)
    ws_count = await session.scalar(
        select(Workspace).where(Workspace.owner_id == user_id)
    )
    assert ws_count is None


async def test_purge_refuses_when_workspace_has_co_member(
    session: AsyncSession,
) -> None:
    """Alice owns a shared workspace where Bob is also a member. Purging
    Alice must NOT delete the shared workspace — refuse instead."""
    alice = await _signup(session, "alice-shared-a3@example.com")
    bob = await _signup(session, "bob-shared-a3@example.com")

    alice_ws = (
        await session.execute(
            select(Workspace).where(Workspace.owner_id == alice.id)
        )
    ).scalar_one()
    await _add_member(session, workspace_id=alice_ws.id, user_id=bob.id)
    await session.commit()

    with pytest.raises(ConflictError) as exc_info:
        await account_purge.purge(session, alice.id)

    assert "transfer ownership" in str(exc_info.value).lower() or \
           "remove members" in str(exc_info.value).lower()
    # Alice + workspace still exist
    assert (
        await session.execute(select(User).where(User.id == alice.id))
    ).scalar_one_or_none() is not None


async def test_purge_cascades_through_projects(session: AsyncSession) -> None:
    user = await _signup(session, "purge-projects-a3@example.com")
    ws = (
        await session.execute(
            select(Workspace).where(Workspace.owner_id == user.id)
        )
    ).scalar_one()

    proj = Project(
        id=new_ulid(),
        workspace_id=ws.id,
        slug="cascade-test",
        name="Cascade",
        pitch="Should cascade-delete",
        status="building",
    )
    session.add(proj)
    await session.flush()
    proj_id = proj.id

    await account_purge.purge(session, user.id)
    await session.commit()

    # Project gone via workspace cascade
    assert (
        await session.execute(select(Project).where(Project.id == proj_id))
    ).scalar_one_or_none() is None
    # WorkspaceKey gone
    assert (
        await session.execute(
            select(WorkspaceKey).where(WorkspaceKey.workspace_id == ws.id)
        )
    ).scalar_one_or_none() is None
