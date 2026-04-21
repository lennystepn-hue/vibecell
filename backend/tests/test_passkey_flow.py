"""Tests for WebAuthn passkey registration + authentication flow.

Mocks the webauthn library and Redis; exercises all 4 endpoints.
Does NOT require a live DB or Redis (pure unit-style).
"""
from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.core.ulid import new_ulid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


FAKE_CHALLENGE = b"fake-challenge-bytes-1234567890"
FAKE_CHALLENGE_B64 = _b64(FAKE_CHALLENGE)
FAKE_CRED_ID = b"fake-credential-id-abc123"
FAKE_CRED_ID_B64 = _b64(FAKE_CRED_ID)
FAKE_PUB_KEY = b"fake-public-key-bytes"
FAKE_PUB_KEY_B64 = _b64(FAKE_PUB_KEY)


def _mock_reg_options() -> MagicMock:
    opts = MagicMock()
    opts.challenge = FAKE_CHALLENGE
    return opts


def _mock_reg_verification() -> MagicMock:
    v = MagicMock()
    v.credential_id = FAKE_CRED_ID
    v.credential_public_key = FAKE_PUB_KEY
    v.sign_count = 0
    return v


def _mock_auth_options() -> MagicMock:
    opts = MagicMock()
    opts.challenge = FAKE_CHALLENGE
    return opts


def _mock_auth_verification() -> MagicMock:
    v = MagicMock()
    v.new_sign_count = 1
    return v


# ---------------------------------------------------------------------------
# Unit tests for the service layer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_registration_stores_challenge(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_registration should call generate_registration_options + store challenge in Redis."""
    import app.services.passkey as svc

    fake_user = MagicMock()
    fake_user.passkey_credentials = []

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock()

    # Patch _get_rp to avoid real settings
    monkeypatch.setattr(svc, "_get_rp", lambda: ("vibecell.dev", "Vibecell", "https://vibecell.dev"))

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_db():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(
            scalar_one_or_none=MagicMock(return_value=fake_user)
        ))
        yield db

    monkeypatch.setattr(svc, "_db_context", _fake_db)

    mock_opts = _mock_reg_options()

    with (
        patch("webauthn.generate_registration_options", return_value=mock_opts) as mock_gen,
        patch("webauthn.options_to_json", return_value='{"type":"reg"}'),
        patch("app.services.passkey.get_redis", new_callable=AsyncMock, return_value=mock_redis),
    ):
        result = await svc.start_registration("user-123", "test@example.com")

    assert mock_gen.called
    assert result == {"type": "reg"}
    mock_redis.set.assert_called_once()


@pytest.mark.asyncio
async def test_finish_registration_no_challenge_raises_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """finish_registration should raise 400 when no challenge found in Redis."""
    import app.services.passkey as svc

    monkeypatch.setattr(svc, "_get_rp", lambda: ("vibecell.dev", "Vibecell", "https://vibecell.dev"))

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.services.passkey.get_redis", new_callable=AsyncMock, return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await svc.finish_registration("user-123", {"id": "cred", "response": {}})

    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail


@pytest.mark.asyncio
async def test_start_authentication_no_user_raises_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_authentication should raise 404 when user doesn't exist."""
    import app.services.passkey as svc

    monkeypatch.setattr(svc, "_get_rp", lambda: ("vibecell.dev", "Vibecell", "https://vibecell.dev"))

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_db():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(
            scalar_one_or_none=MagicMock(return_value=None)
        ))
        yield db

    monkeypatch.setattr(svc, "_db_context", _fake_db)

    with pytest.raises(HTTPException) as exc_info:
        await svc.start_authentication("nonexistent@example.com")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_start_authentication_no_credentials_raises_404(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_authentication should raise 404 when user has no passkeys."""
    import app.services.passkey as svc

    monkeypatch.setattr(svc, "_get_rp", lambda: ("vibecell.dev", "Vibecell", "https://vibecell.dev"))

    fake_user = MagicMock()
    fake_user.passkey_credentials = []  # no passkeys

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_db():
        db = AsyncMock()
        db.execute = AsyncMock(return_value=AsyncMock(
            scalar_one_or_none=MagicMock(return_value=fake_user)
        ))
        yield db

    monkeypatch.setattr(svc, "_db_context", _fake_db)

    with pytest.raises(HTTPException) as exc_info:
        await svc.start_authentication("test@example.com")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_finish_authentication_no_challenge_raises_400(monkeypatch: pytest.MonkeyPatch) -> None:
    """finish_authentication should raise 400 when no challenge in Redis."""
    import app.services.passkey as svc

    monkeypatch.setattr(svc, "_get_rp", lambda: ("vibecell.dev", "Vibecell", "https://vibecell.dev"))

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)

    with patch("app.services.passkey.get_redis", new_callable=AsyncMock, return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await svc.finish_authentication("test@example.com", {"id": "cred"})

    assert exc_info.value.status_code == 400
    assert "expired" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Integration-style endpoint smoke tests (no real DB or Redis)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_begin_endpoint_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/passkey/register/begin should call start_registration and return 200."""
    from app.main import app

    async def fake_start_registration(user_id: str, user_email: str) -> dict:
        return {"challenge": "abc", "rp": {"id": "vibecell.dev"}}

    monkeypatch.setattr("app.services.passkey.start_registration", fake_start_registration)

    # We need to inject an authenticated user into request.state
    from app.core.db import get_db
    from app.core.deps import require_auth, AuthContext

    fake_user = MagicMock()
    fake_user.id = new_ulid()
    fake_user.email = "test@example.com"
    fake_ctx = AuthContext(user=fake_user, active_workspace_id=new_ulid())

    app.dependency_overrides[require_auth] = lambda: fake_ctx
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t"
        ) as c:
            r = await c.post("/api/v1/passkey/register/begin")
        assert r.status_code == 200
        assert "challenge" in r.json()
    finally:
        app.dependency_overrides.pop(require_auth, None)


@pytest.mark.asyncio
async def test_auth_begin_endpoint_calls_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/passkey/auth/begin should call start_authentication."""
    from app.main import app

    async def fake_start_auth(email: str) -> dict:
        return {"challenge": "xyz", "allowCredentials": []}

    monkeypatch.setattr("app.services.passkey.start_authentication", fake_start_auth)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/v1/passkey/auth/begin",
            json={"email": "test@example.com"},
        )
    assert r.status_code == 200
    assert "challenge" in r.json()


@pytest.mark.asyncio
async def test_auth_finish_endpoint_sets_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/passkey/auth/finish should set hangar_session cookie on success."""
    from app.main import app

    fake_session_id = new_ulid()

    async def fake_finish_auth(email: str, assertion_response: dict) -> str:
        return fake_session_id

    monkeypatch.setattr("app.services.passkey.finish_authentication", fake_finish_auth)
    # session_cookie_attrs calls get_settings; stub it so no DB URL needed
    monkeypatch.setattr(
        "app.api.v1.passkey.session_cookie_attrs",
        lambda: {"key": "hangar_session", "httponly": True, "path": "/"},
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post(
            "/api/v1/passkey/auth/finish",
            json={"email": "test@example.com", "assertion": {"id": "cred"}},
        )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "hangar_session" in r.cookies


@pytest.mark.asyncio
async def test_register_finish_endpoint_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /api/v1/passkey/register/finish should return {ok: true}."""
    from app.main import app
    from app.core.deps import require_auth, AuthContext

    async def fake_finish_reg(user_id: str, credential_response: dict) -> bool:
        return True

    monkeypatch.setattr("app.services.passkey.finish_registration", fake_finish_reg)

    fake_user = MagicMock()
    fake_user.id = new_ulid()
    fake_user.email = "test@example.com"
    fake_ctx = AuthContext(user=fake_user, active_workspace_id=new_ulid())

    app.dependency_overrides[require_auth] = lambda: fake_ctx
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post(
                "/api/v1/passkey/register/finish",
                json={"credential": {"id": "cred", "rawId": "cred", "response": {}}},
            )
        assert r.status_code == 200
        assert r.json()["ok"] is True
    finally:
        app.dependency_overrides.pop(require_auth, None)
