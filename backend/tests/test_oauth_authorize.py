"""Integration tests for GET /oauth/authorize, POST /oauth/grant, POST /oauth/deny."""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def authed_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """An AsyncClient that is signed in as a test user (session cookie set)."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-test@example.com")
            yield c
    finally:
        clear_db_override()


@pytest_asyncio.fixture
async def user_workspace(session: AsyncSession, authed_client: AsyncClient):
    """Return the Workspace that was auto-created for the signed-in user."""
    from app.models import User, Workspace, WorkspaceMember

    user = (await session.execute(
        select(User).where(User.email == "oauth-test@example.com")
    )).scalar_one()

    ws = (await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .limit(1)
    )).scalar_one()
    return ws


async def test_authorize_requires_signin(session: AsyncSession, registered_oauth_client) -> None:
    """Unauth'd call → 302 redirect to /login with ?next= param."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as client:
            cid = registered_oauth_client.client_id
            resp = await client.get(
                f"/oauth/authorize?response_type=code&client_id={cid}"
                "&redirect_uri=http://127.0.0.1:1/cb"
                "&code_challenge=abc&code_challenge_method=S256&state=xyz&scope=vibecell:tools",
                follow_redirects=False,
            )
    finally:
        clear_db_override()
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login?next=")


async def test_authorize_returns_consent_context(
    authed_client: AsyncClient, registered_oauth_client
) -> None:
    cid = registered_oauth_client.client_id
    resp = await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=xyz&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["client_id"] == cid
    assert body["client_name"] is not None
    assert isinstance(body["workspaces"], list)
    assert body["state"] == "xyz"


async def test_grant_issues_code(
    authed_client: AsyncClient, registered_oauth_client, user_workspace
) -> None:
    cid = registered_oauth_client.client_id
    get_resp = await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=s1&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    assert get_resp.status_code == 200

    resp = await authed_client.post(
        "/oauth/grant",
        json={"state": "s1", "workspace_id": user_workspace.id},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    loc = resp.headers["location"]
    assert loc.startswith("http://127.0.0.1:1/cb?code=")
    assert "&state=s1" in loc


async def test_grant_invalid_workspace_rejected(
    authed_client: AsyncClient, registered_oauth_client
) -> None:
    cid = registered_oauth_client.client_id
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=s2&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    resp = await authed_client.post(
        "/oauth/grant",
        json={"state": "s2", "workspace_id": "01BADWORKSPACE0000000000000"},
    )
    assert resp.status_code == 403
