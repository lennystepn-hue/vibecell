import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import ProjectRepo
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def test_resync_updates_metadata(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            # Setup connection
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
            })
            await sign_in(c, session, "resync@example.com")
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]

            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "resync@example.com")
            )).scalar_one()

            redis = await get_redis()
            await redis.set("gh-oauth-state:s", f"{ws_id}:{user_id}", ex=300)
            await c.get("/api/v1/integrations/github/oauth-callback?code=c&state=s")

            # Create project with GitHub repo via import
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "v1",
                    "private": False,
                    "default_branch": "main",
                    "language": "Python",
                    "license": {"spdx_id": "MIT"},
                    "homepage": None,
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-18T10:00:00Z",
                },
            })
            await c.post(
                "/api/v1/integrations/github/import",
                json={"repos": [{"owner": "lenny", "name": "butlr"}]},
            )

            # Resync with updated metadata
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "v2",
                    "private": False,
                    "default_branch": "develop",
                    "language": "Rust",
                    "license": {"spdx_id": "Apache-2.0"},
                    "homepage": None,
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-19T10:00:00Z",
                },
            })
            resp = await c.post("/api/v1/projects/butlr/repo/resync")
    finally:
        clear_db_override()

    assert resp.status_code == 200

    repo = (await session.execute(
        select(ProjectRepo).where(ProjectRepo.git_url == "https://github.com/lenny/butlr.git")
    )).scalar_one()
    assert repo.default_branch == "develop"
    assert repo.primary_lang == "Rust"
    assert repo.license == "Apache-2.0"
