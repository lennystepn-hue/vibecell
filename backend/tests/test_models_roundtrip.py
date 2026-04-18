from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import (
    ActiveProject,
    AuditLog,
    CliDevice,
    Integration,
    MagicLinkToken,
    Project,
    ProjectCommand,
    ProjectContext,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
    ProjectRepo,
    ProjectStack,
    ProjectTag,
    StackItem,
    Tag,
    User,
    Workspace,
    WorkspaceKey,
    WorkspaceMember,
)

pytestmark = pytest.mark.integration


async def _make_base(session: AsyncSession) -> tuple[str, str, str]:
    """Create user + workspace + project; return their IDs."""
    user = User(email=f"u-{new_ulid()}@example.com", name="Test User", handle=f"h-{new_ulid()[:10]}")
    session.add(user)
    await session.flush()

    workspace = Workspace(slug=f"ws-{new_ulid()[:10]}", name="Test WS", owner_id=user.id)
    session.add(workspace)
    await session.flush()

    session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))

    project = Project(
        workspace_id=workspace.id,
        slug="butlr",
        name="Butlr",
        emoji="🛎️",
        pitch="OpenClaw-as-a-Service",
        status="building",
    )
    session.add(project)
    await session.flush()

    return user.id, workspace.id, project.id


async def test_full_project_aggregate_roundtrip(session: AsyncSession) -> None:
    user_id, workspace_id, project_id = await _make_base(session)

    # Children
    session.add(ProjectRepo(
        project_id=project_id, role="monorepo",
        git_url="git@github.com:lenny/butlr.git", primary_lang="Python",
    ))
    session.add(ProjectEnvironment(project_id=project_id, kind="prod", url="https://butlr.cloud"))
    session.add(ProjectInfra(
        project_id=project_id, server_alias="butlr-prod",
        domain_primary="butlr.cloud", domains=["butlr.cloud", "butlr.app"],
    ))
    session.add(ProjectContext(
        project_id=project_id,
        current_focus="Stripe webhook",
        next_step="Handle subscription.deleted",
        open_questions=["Pro-rata on upgrades?"],
    ))
    session.add(ProjectLink(project_id=project_id, kind="live", label="Live", url="https://butlr.cloud"))
    session.add(ProjectCommand(project_id=project_id, label="Deploy", command="make deploy"))

    # Stack
    stack = StackItem(slug=f"custom-{new_ulid()[:10]}", name="Custom", kind="lib")
    session.add(stack)
    await session.flush()
    session.add(ProjectStack(project_id=project_id, stack_item_id=stack.id, role="primary"))

    # Tag
    tag = Tag(workspace_id=workspace_id, name="backend", color="#8ab4ff")
    session.add(tag)
    await session.flush()
    session.add(ProjectTag(project_id=project_id, tag_id=tag.id))

    # Active project
    session.add(ActiveProject(workspace_id=workspace_id, user_id=user_id, project_id=project_id))

    # Integration + workspace key
    session.add(WorkspaceKey(workspace_id=workspace_id, dek_ciphertext="nonce.ciphertext.tag"))
    session.add(Integration(workspace_id=workspace_id, kind="github", config={"login": "lenny"}))

    # CLI device
    session.add(CliDevice(
        user_id=user_id, name="macbook", paired_at=datetime.now(UTC),
        token_hash="deadbeef" * 8,
    ))

    # Magic link token
    session.add(MagicLinkToken(
        email="u@example.com", token_hash="aa" * 32,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    ))

    # Audit entry (manual for now; automated listener lands in Phase 2)
    session.add(AuditLog(
        workspace_id=workspace_id, actor=f"ui:{user_id}", op="create",
        entity="projects", entity_id=project_id, diff={"name": [None, "Butlr"]},
    ))

    await session.flush()

    # Re-read and verify
    proj = (await session.execute(
        select(Project).where(Project.id == project_id)
    )).scalar_one()
    assert proj.slug == "butlr"
    assert proj.status == "building"
    assert proj.created_at is not None
    assert proj.updated_at is not None

    ctx = (await session.execute(
        select(ProjectContext).where(ProjectContext.project_id == project_id)
    )).scalar_one()
    assert ctx.current_focus == "Stripe webhook"
    assert ctx.open_questions == ["Pro-rata on upgrades?"]

    infra = (await session.execute(
        select(ProjectInfra).where(ProjectInfra.project_id == project_id)
    )).scalar_one()
    assert infra.domains == ["butlr.cloud", "butlr.app"]

    # Verify FK cascade: deleting workspace removes everything
    ws = (await session.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )).scalar_one()
    await session.delete(ws)
    await session.flush()

    remaining_projects = (await session.execute(
        select(Project).where(Project.workspace_id == workspace_id)
    )).scalars().all()
    assert len(remaining_projects) == 0

    remaining_tags = (await session.execute(
        select(Tag).where(Tag.workspace_id == workspace_id)
    )).scalars().all()
    assert len(remaining_tags) == 0


async def test_unique_slug_per_workspace(session: AsyncSession) -> None:
    _user_id, workspace_id, _ = await _make_base(session)

    session.add(Project(workspace_id=workspace_id, slug="duplicate", name="First"))
    await session.flush()

    session.add(Project(workspace_id=workspace_id, slug="duplicate", name="Second"))

    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_slug_same_across_workspaces_allowed(session: AsyncSession) -> None:
    # Two workspaces, each with a project slug "shared" — should not conflict.
    user_a = User(email=f"a-{new_ulid()}@example.com")
    user_b = User(email=f"b-{new_ulid()}@example.com")
    session.add_all([user_a, user_b])
    await session.flush()

    ws_a = Workspace(slug=f"a-{new_ulid()[:10]}", name="A", owner_id=user_a.id)
    ws_b = Workspace(slug=f"b-{new_ulid()[:10]}", name="B", owner_id=user_b.id)
    session.add_all([ws_a, ws_b])
    await session.flush()

    session.add_all([
        Project(workspace_id=ws_a.id, slug="shared", name="Shared A"),
        Project(workspace_id=ws_b.id, slug="shared", name="Shared B"),
    ])
    await session.flush()  # should not raise
