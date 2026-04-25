"""Tests for portfolio snapshot caching (Spec 5B.1).

- First call generates + persists.
- Second call returns cached row (same snapshot_id).
- ?refresh=true forces regeneration (new snapshot_id).
Requires a real DB (integration test).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import User, Workspace, WorkspaceMember
from app.models.signals import PortfolioSnapshot

pytestmark = pytest.mark.integration


async def _make_workspace(session: AsyncSession) -> tuple[str, str]:
    """Return (user_id, workspace_id)."""
    user = User(id=new_ulid(), email=f"port-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()

    ws = Workspace(id=new_ulid(), slug=f"ws-{new_ulid()[:8]}", name="Portfolio WS", owner_id=user.id)
    session.add(ws)
    await session.flush()
    session.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner"))
    await session.flush()
    return user.id, ws.id


@pytest.mark.asyncio
async def test_generate_snapshot_persists_row(session: AsyncSession) -> None:
    """generate_snapshot() should insert a row into portfolio_snapshot."""
    _, workspace_id = await _make_workspace(session)

    from app.services.portfolio_intel import generate_snapshot

    before = (await session.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.workspace_id == workspace_id)
    )).scalars().all()
    assert len(before) == 0

    result = await generate_snapshot(workspace_id, session)

    after = (await session.execute(
        select(PortfolioSnapshot).where(PortfolioSnapshot.workspace_id == workspace_id)
    )).scalars().all()
    assert len(after) == 1
    assert after[0].data["workspace_id"] == workspace_id
    assert result["workspace_id"] == workspace_id


@pytest.mark.asyncio
async def test_get_or_generate_caches_second_call(session: AsyncSession) -> None:
    """Second call within cache window returns same snapshot_id."""
    _, workspace_id = await _make_workspace(session)

    from app.services.portfolio_intel import get_or_generate

    first = await get_or_generate(workspace_id, session)
    assert first["_cache_hit"] is False
    first_id = first["_snapshot_id"]
    assert first_id is not None

    second = await get_or_generate(workspace_id, session)
    assert second["_cache_hit"] is True
    assert second["_snapshot_id"] == first_id


@pytest.mark.asyncio
async def test_get_or_generate_refresh_forces_new_snapshot(session: AsyncSession) -> None:
    """?refresh=true should generate a new snapshot even within the cache window."""
    _, workspace_id = await _make_workspace(session)

    from app.services.portfolio_intel import get_or_generate

    first = await get_or_generate(workspace_id, session)
    first_id = first["_snapshot_id"]

    forced = await get_or_generate(workspace_id, session, force=True)
    assert forced["_cache_hit"] is False
    assert forced["_snapshot_id"] != first_id


@pytest.mark.asyncio
async def test_get_snapshot_endpoint_with_refresh(session: AsyncSession) -> None:
    """GET /api/v1/portfolio/snapshot?refresh=true returns a fresh snapshot."""
    from app.core.deps import AuthContext, require_auth
    from app.main import app
    from tests._auth_helpers import clear_db_override, override_db

    _, workspace_id = await _make_workspace(session)

    fake_user_obj = User(id=new_ulid(), email="snap-test@example.com")
    fake_ctx = AuthContext(user=fake_user_obj, active_workspace_id=workspace_id)

    override_db(session)
    app.dependency_overrides[require_auth] = lambda: fake_ctx
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r1 = await c.get("/api/v1/portfolio/snapshot")
            assert r1.status_code == 200
            snap1 = r1.json()
            assert snap1["workspace_id"] == workspace_id
            id1 = snap1.get("_snapshot_id")

            r2 = await c.get("/api/v1/portfolio/snapshot")
            assert r2.status_code == 200
            snap2 = r2.json()
            assert snap2["_cache_hit"] is True
            assert snap2["_snapshot_id"] == id1

            r3 = await c.get("/api/v1/portfolio/snapshot?refresh=true")
            assert r3.status_code == 200
            snap3 = r3.json()
            assert snap3["_cache_hit"] is False
            assert snap3["_snapshot_id"] != id1
    finally:
        app.dependency_overrides.pop(require_auth, None)
        clear_db_override()
