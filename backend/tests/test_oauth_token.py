"""Integration tests for POST /oauth/token — code exchange + refresh rotation."""
from __future__ import annotations

import base64
import hashlib
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


def _pkce_pair() -> tuple[str, str]:
    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


@pytest_asyncio.fixture
async def client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """An unauthenticated AsyncClient (for /oauth/token calls)."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            yield c
    finally:
        clear_db_override()


@pytest_asyncio.fixture
async def authed_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """An AsyncClient signed in as the oauth-token test user."""
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-token-test@example.com")
            yield c
    finally:
        clear_db_override()


@pytest_asyncio.fixture
async def user_workspace(session: AsyncSession, authed_client: AsyncClient):
    """Return the Workspace auto-created for the signed-in user."""
    from app.models import User, Workspace, WorkspaceMember

    user = (await session.execute(
        select(User).where(User.email == "oauth-token-test@example.com")
    )).scalar_one()

    ws = (await session.execute(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .limit(1)
    )).scalar_one()
    return ws


async def test_token_code_exchange_happy_path(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]

    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s1&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    r = await authed_client.post(
        "/oauth/grant",
        json={"state": "s1", "workspace_id": user_workspace.id},
        follow_redirects=False,
    )
    loc = r.headers["location"]
    code = loc.split("code=")[1].split("&")[0]

    resp = await client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect,
            "client_id": cid,
            "code_verifier": verifier,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600
    assert body["access_token"].count(".") == 2
    assert body["refresh_token"].startswith("rt_")


async def test_token_rejects_wrong_pkce_verifier(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s2&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    r = await authed_client.post("/oauth/grant", json={"state": "s2", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]

    resp = await client.post("/oauth/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "client_id": cid,
        "code_verifier": "wrong_verifier_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    })
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "invalid_grant"


async def test_token_code_single_use(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s3&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    r = await authed_client.post("/oauth/grant", json={"state": "s3", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect,
        "client_id": cid,
        "code_verifier": verifier,
    }
    ok = await client.post("/oauth/token", data=data)
    assert ok.status_code == 200

    again = await client.post("/oauth/token", data=data)
    assert again.status_code == 400
    assert again.json()["detail"]["error"] == "invalid_grant"


async def test_refresh_token_rotation(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s4&scope=vibecell:tools",
        headers={"accept": "application/json"},
    )
    r = await authed_client.post("/oauth/grant", json={"state": "s4", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]
    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
        "client_id": cid, "code_verifier": verifier,
    })).json()
    rt = tok["refresh_token"]

    r2 = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert r2.status_code == 200
    new_pair = r2.json()
    assert new_pair["refresh_token"] != rt
    assert new_pair["access_token"] != tok["access_token"]

    r3 = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert r3.status_code == 400
    assert r3.json()["detail"]["error"] == "invalid_grant"
