"""Integration tests for the CLI device-code pairing flow."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.middleware import set_bearer_session_factory
from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _shared_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Yield the test session as a no-close, no-commit context manager.

    The test's outer transaction is rolled back by the `session` fixture;
    commits inside the middleware would otherwise be no-ops on the outer
    connection anyway, so just yield without closing.
    """
    yield session


def _install_middleware_session(session: AsyncSession) -> None:
    set_bearer_session_factory(lambda: _shared_session(session))


def _clear_middleware_session() -> None:
    set_bearer_session_factory(None)


async def _poll_complete(
    c: AsyncClient, device_code: str, *, attempts: int = 5, delay_s: float = 0.1
) -> dict[str, object]:
    """Poll /pair/complete until it returns 200 or we exceed `attempts`."""
    for _ in range(attempts):
        r = await c.post("/api/v1/cli/pair/complete", json={"device_code": device_code})
        if r.status_code == 200:
            body: dict[str, object] = r.json()
            return body
        assert r.status_code == 202, f"unexpected status {r.status_code}: {r.text}"
        await asyncio.sleep(delay_s)
    raise AssertionError("pair/complete never returned 200")


async def test_pair_full_flow(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    override_db(session)
    _install_middleware_session(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            # 1) CLI kicks off pairing (anonymous).
            r = await c.post("/api/v1/cli/pair/start")
            assert r.status_code == 200, r.text
            start = r.json()
            device_code = start["device_code"]
            user_code = start["user_code"]
            assert len(user_code) == 9 and user_code[4] == "-"
            assert start["expires_in"] == 600

            # 2) Poll before confirm → 202.
            r = await c.post("/api/v1/cli/pair/complete", json={"device_code": device_code})
            assert r.status_code == 202
            assert r.json()["status"] == "pending"

            # 3) Browser signs in + confirms.
            await sign_in(c, session, "pair-flow@example.com")
            r = await c.post(
                "/api/v1/cli/pair/confirm",
                json={"user_code": user_code, "device_name": "mac"},
            )
            assert r.status_code == 204, r.text

            # 4) Poll again → 200 + token.
            body = await _poll_complete(c, device_code)
            assert "token" in body and isinstance(body["token"], str)
            assert body["workspace_slug"]
            token = body["token"]
            device_id = body["device_id"]

        # 5) New client — bearer token works on /api/v1/me.
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c2:
            r = await c2.get(
                "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 200, r.text
            assert r.json()["user"]["email"] == "pair-flow@example.com"

        # 6) Second poll after success returns 202 (key was consumed).
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c3:
            r = await c3.post(
                "/api/v1/cli/pair/complete", json={"device_code": device_code}
            )
            assert r.status_code == 202

        assert device_id  # sanity
    finally:
        _clear_middleware_session()
        clear_db_override()


async def test_pair_complete_pending_returns_202(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    override_db(session)
    _install_middleware_session(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            r = await c.post("/api/v1/cli/pair/start")
            assert r.status_code == 200
            device_code = r.json()["device_code"]

            r = await c.post(
                "/api/v1/cli/pair/complete", json={"device_code": device_code}
            )
            assert r.status_code == 202
            assert r.json() == {"status": "pending"}
    finally:
        _clear_middleware_session()
        clear_db_override()


async def test_revoke_device_invalidates_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    override_db(session)
    _install_middleware_session(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c:
            # Pair
            r = await c.post("/api/v1/cli/pair/start")
            start = r.json()
            device_code = start["device_code"]
            user_code = start["user_code"]

            await sign_in(c, session, "revoke-test@example.com")
            r = await c.post(
                "/api/v1/cli/pair/confirm",
                json={"user_code": user_code, "device_name": "linux"},
            )
            assert r.status_code == 204

            body = await _poll_complete(c, device_code)
            token = body["token"]
            device_id = body["device_id"]

            # Token works
            r = await c.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200

            # Revoke (browser-side, uses cookie auth on same client)
            r = await c.delete(f"/api/v1/cli/devices/{device_id}")
            assert r.status_code == 204

        # New client — bearer should now fail (device deleted).
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://t",
            follow_redirects=False,
        ) as c2:
            r = await c2.get(
                "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
            )
            assert r.status_code == 401
    finally:
        _clear_middleware_session()
        clear_db_override()
