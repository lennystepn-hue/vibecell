import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import ActiveProject, Workspace
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_switch_sets_active_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "switch-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "alpha", "name": "A"})
            await c.post("/api/v1/projects", json={"slug": "beta", "name": "B"})
            r1 = await c.post("/api/v1/projects/beta/switch")
    finally:
        clear_db_override()
    assert r1.status_code == 200
    assert r1.json()["slug"] == "beta"

    # Verify ActiveProject row was written
    wsq = await session.execute(select(Workspace).where(Workspace.slug.icontains("switch-p")))
    ws = wsq.scalar_one()
    ap = (await session.execute(
        select(ActiveProject).where(ActiveProject.workspace_id == ws.id)
    )).scalar_one()
    assert ap.project_id  # set


async def test_switch_404_for_unknown_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "switch-missing@example.com")
            resp = await c.post("/api/v1/projects/nope/switch")
    finally:
        clear_db_override()
    assert resp.status_code == 404
