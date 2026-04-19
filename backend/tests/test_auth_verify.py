from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.models import Workspace, WorkspaceKey, WorkspaceMember
from app.services.login import issue_magic_link

pytestmark = pytest.mark.integration


def _override_db(session: AsyncSession) -> None:
    """Route get_db to the test's wrapping-tx session so the HTTP handler sees
    the data that issue_magic_link wrote. Caller must restore after the test."""
    async def _fake_get_db() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_db] = _fake_get_db


def _clear_db_override() -> None:
    app.dependency_overrides.pop(get_db, None)


async def test_verify_first_login_creates_user_workspace_and_dek(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    # Seed a magic-link token the way POST /auth/magic-link would.
    raw_token = await issue_magic_link(session, email="new-user@example.com")
    await session.flush()

    _override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            resp = await c.get(f"/api/v1/auth/verify?token={raw_token}")
    finally:
        _clear_db_override()

    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "hangar_session" in resp.headers.get("set-cookie", "")

    # Verify the bootstrap side effects
    ws = (await session.execute(
        select(Workspace).where(
            Workspace.name.icontains("New User") | Workspace.slug.icontains("new-user")
        )
    )).scalar_one_or_none()
    assert ws is not None
    members = (await session.execute(
        select(WorkspaceMember).where(WorkspaceMember.workspace_id == ws.id)
    )).scalars().all()
    assert len(members) == 1
    key = (await session.execute(
        select(WorkspaceKey).where(WorkspaceKey.workspace_id == ws.id)
    )).scalar_one_or_none()
    assert key is not None
    assert key.dek_ciphertext  # non-empty wrapped DEK


async def test_verify_rejects_expired_token(session: AsyncSession) -> None:
    import hashlib
    import secrets as _secrets
    from datetime import UTC, datetime, timedelta

    from app.core.ulid import new_ulid
    from app.models import MagicLinkToken

    raw = _secrets.token_urlsafe(32)
    token = MagicLinkToken(
        id=new_ulid(), email="expired@example.com",
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(token)
    await session.flush()

    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.get(f"/api/v1/auth/verify?token={raw}")
    finally:
        _clear_db_override()
    assert resp.status_code == 401


async def test_verify_rejects_reused_token(session: AsyncSession) -> None:
    raw = await issue_magic_link(session, email="reuse@example.com")
    await session.flush()

    _override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            r1 = await c.get(f"/api/v1/auth/verify?token={raw}")
            r2 = await c.get(f"/api/v1/auth/verify?token={raw}")
    finally:
        _clear_db_override()

    assert r1.status_code == 303
    assert r2.status_code == 401


async def test_logout_clears_cookie() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post(
            "/api/v1/auth/logout",
            cookies={"hangar_session": "01FAKE00000000000000000000"},
        )
    assert resp.status_code == 204
    set_cookie = resp.headers.get("set-cookie", "")
    assert 'hangar_session=""' in set_cookie or "hangar_session=;" in set_cookie
