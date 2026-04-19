import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Project, ProjectRepo
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def _setup_connected(
    c: AsyncClient, session: AsyncSession, email: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake",
        "me": {"login": "lenny"},
    })
    await sign_in(c, session, email)
    me = (await c.get("/api/v1/me")).json()
    ws_slug = me["active_workspace"]["slug"]

    from app.models import User, Workspace
    ws_id = (await session.execute(
        select(Workspace.id).where(Workspace.slug == ws_slug)
    )).scalar_one()
    user_id = (await session.execute(
        select(User.id).where(User.email == email)
    )).scalar_one()

    redis = await get_redis()
    state = f"state-{email}"
    await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
    r = await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")
    assert r.status_code == 303


async def test_import_creates_projects_with_repos_and_links(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await _setup_connected(c, session, "import@example.com", monkeypatch)

            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "OpenClaw-as-a-Service",
                    "private": True,
                    "default_branch": "main",
                    "language": "Python",
                    "license": {"spdx_id": "MIT"},
                    "homepage": "https://butlr.cloud",
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-18T10:00:00Z",
                },
            })
            resp = await c.post(
                "/api/v1/integrations/github/import",
                json={"repos": [{"owner": "lenny", "name": "butlr"}]},
            )
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "imported"
    assert body["results"][0]["slug"] == "butlr"

    project = (await session.execute(
        select(Project).where(Project.slug == "butlr")
    )).scalar_one()
    assert project.pitch == "OpenClaw-as-a-Service"

    repo = (await session.execute(
        select(ProjectRepo).where(ProjectRepo.project_id == project.id)
    )).scalar_one()
    assert repo.git_url == "https://github.com/lenny/butlr.git"
    assert repo.primary_lang == "Python"
    assert repo.license == "MIT"
