# Phase 3 — Auth (magic-link + session + middleware)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Ship the first three public API routes (`POST /auth/magic-link`, `GET /auth/verify`, `POST /auth/logout`) wired end-to-end: Resend integration for delivering magic-link emails, Redis-backed sessions, session-cookie middleware, first-login bootstrap that creates a user + default workspace + workspace_keys DEK, rate-limiting on auth endpoints, and an exception handler mapping `HangarError` → RFC 7807 Problem+JSON.

**Architecture:** One new router module `app/api/v1/auth.py`, one Resend wrapper `app/services/mailer.py`, session middleware in `app/core/middleware.py`, and a login-bootstrap service in `app/services/login.py`. FastAPI's dependency-injection wires the Redis session store + the audit context-vars. Errors hit an app-level handler that converts `HangarError.to_problem()` to `JSONResponse`. Tests use `httpx.ASGITransport` + the Phase 1 conftest to drive the full stack.

**Tech Stack:** FastAPI routing + Depends, Resend SDK for email, Redis for session store, `itsdangerous` for token comparison, `secrets` for magic-link token generation.

**Prerequisite:** Phase 2 complete (HEAD ≥ `00269c3`). All core utilities available.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── auth.py                    POST /auth/magic-link, GET /auth/verify, POST /auth/logout
│   ├── core/
│   │   ├── middleware.py                  session + audit context middleware
│   │   ├── session.py                     Redis session store (read/write/delete)
│   │   └── problem.py                     HangarError → JSONResponse handler
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py                        MagicLinkRequest, Me
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mailer.py                      Resend wrapper (with dev-mode log fallback)
│   │   └── login.py                       magic-link issue + verify + first-login bootstrap
│   └── main.py                            (modified) mounts auth router + exception handler + middleware
└── tests/
    ├── test_session_store.py
    ├── test_mailer.py
    ├── test_auth_magic_link.py
    └── test_auth_verify.py
```

---

## Task 3.1 — Redis session store

**Files:**
- Create: `backend/app/core/session.py`
- Create: `backend/tests/test_session_store.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_session_store.py
import pytest

from app.core.session import (
    SessionPayload,
    create_session,
    delete_session,
    get_session,
)

pytestmark = pytest.mark.integration


async def test_create_then_get_roundtrip() -> None:
    session_id = await create_session(
        SessionPayload(user_id="01USER", workspace_id="01WS"), ttl_seconds=60,
    )
    assert isinstance(session_id, str)
    assert len(session_id) == 26

    payload = await get_session(session_id)
    assert payload is not None
    assert payload.user_id == "01USER"
    assert payload.workspace_id == "01WS"

    await delete_session(session_id)
    assert await get_session(session_id) is None


async def test_get_returns_none_for_missing() -> None:
    assert await get_session("01NOTEXIST" + "0" * 16) is None


async def test_expired_session_returns_none() -> None:
    import asyncio
    session_id = await create_session(
        SessionPayload(user_id="u", workspace_id="w"), ttl_seconds=1,
    )
    await asyncio.sleep(1.2)
    assert await get_session(session_id) is None
```

- [ ] **Step 2: Write the implementation**

```python
# backend/app/core/session.py
"""Redis-backed session store for web auth.

Sessions are ULIDs; values are JSON-encoded SessionPayload. TTL is the
session cookie Max-Age (default 30 days). Deletion on logout or when
verify detects replay/tampering.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.core.redis import get_redis
from app.core.ulid import new_ulid

_KEY_PREFIX = "session:"


@dataclass(frozen=True, slots=True)
class SessionPayload:
    user_id: str
    workspace_id: str


def _key(session_id: str) -> str:
    return f"{_KEY_PREFIX}{session_id}"


async def create_session(payload: SessionPayload, *, ttl_seconds: int) -> str:
    redis = await get_redis()
    session_id = new_ulid()
    await redis.set(_key(session_id), json.dumps(asdict(payload)), ex=ttl_seconds)
    return session_id


async def get_session(session_id: str) -> SessionPayload | None:
    if not session_id:
        return None
    redis = await get_redis()
    raw = await redis.get(_key(session_id))
    if raw is None:
        return None
    data = json.loads(raw)
    return SessionPayload(user_id=data["user_id"], workspace_id=data["workspace_id"])


async def delete_session(session_id: str) -> None:
    redis = await get_redis()
    await redis.delete(_key(session_id))
```

- [ ] **Step 3: Validate**

```bash
cd backend
uv run ruff check .
uv run mypy app tests
uv run pytest tests/test_session_store.py --collect-only -q
```

Expected: 3 tests collect; full suite still green for DB-free tests.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/session.py backend/tests/test_session_store.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): Redis session store (ULID session ids, JSON payload, TTL)

SessionPayload carries (user_id, workspace_id). 30-day default TTL via
env HANGAR_SESSION_MAX_AGE. Auto-expiry means no GC cron needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.2 — HangarError exception handler → Problem+JSON

**Files:**
- Create: `backend/app/core/problem.py`
- Modify: `backend/app/main.py` (register the handler)
- Create: `backend/tests/test_problem_handler.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_problem_handler.py
from httpx import ASGITransport, AsyncClient

from app.core.errors import NotFoundError, RateLimitedError


async def test_hangar_error_becomes_problem_json() -> None:
    from fastapi import FastAPI

    from app.core.problem import install_problem_handler

    test_app = FastAPI()
    install_problem_handler(test_app)

    @test_app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("project", "butlr")

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://t") as c:
        resp = await c.get("/boom")
    assert resp.status_code == 404
    body = resp.json()
    assert body["type"] == "/errors/not-found"
    assert body["title"] == "Not Found"
    assert body["status"] == 404
    assert "butlr" in body["detail"]


async def test_rate_limited_adds_retry_after_header() -> None:
    from fastapi import FastAPI

    from app.core.problem import install_problem_handler

    test_app = FastAPI()
    install_problem_handler(test_app)

    @test_app.get("/boom")
    async def boom() -> None:
        raise RateLimitedError(detail="slow down", retry_after_s=42)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://t") as c:
        resp = await c.get("/boom")
    assert resp.status_code == 429
    assert resp.headers.get("retry-after") == "42"
    body = resp.json()
    assert body["retry_after_s"] == 42
```

- [ ] **Step 2: Implement**

```python
# backend/app/core/problem.py
"""Map HangarError → RFC 7807 Problem+JSON response."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import HangarError, RateLimitedError


async def _hangar_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HangarError)
    headers: dict[str, str] = {}
    if isinstance(exc, RateLimitedError):
        headers["Retry-After"] = str(exc.extras.get("retry_after_s", 0))
    return JSONResponse(
        status_code=exc.status,
        content=exc.to_problem(),
        headers=headers,
        media_type="application/problem+json",
    )


def install_problem_handler(app: FastAPI) -> None:
    app.add_exception_handler(HangarError, _hangar_error_handler)
```

Modify `backend/app/main.py` to register the handler. Current file ends with:

```python
@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
```

Add after `app = FastAPI(...)`:

```python
from app.core.problem import install_problem_handler

install_problem_handler(app)
```

(Top of file — after the `from fastapi import FastAPI` line.)

- [ ] **Step 3: Run — both tests expected pass**

```bash
uv run pytest tests/test_problem_handler.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/problem.py backend/app/main.py backend/tests/test_problem_handler.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): install HangarError → Problem+JSON exception handler

RateLimitedError additionally emits `Retry-After` header. Media type
set to `application/problem+json` per RFC 7807.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.3 — Resend mailer wrapper

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/mailer.py`
- Create: `backend/tests/test_mailer.py`

In dev mode (`HANGAR_DEV_MODE=1`), the mailer prints emails to logger instead of calling Resend. Production uses Resend SDK.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_mailer.py
import logging

from app.services.mailer import send_magic_link_email


async def test_dev_mode_logs_instead_of_sending(
    monkeypatch, caplog,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    with caplog.at_level(logging.INFO, logger="app.services.mailer"):
        await send_magic_link_email(
            to="u@example.com",
            verify_url="http://localhost:3000/auth/verify?token=abc",
        )

    logs = [rec.message for rec in caplog.records if rec.name == "app.services.mailer"]
    assert any("u@example.com" in msg for msg in logs)
    assert any("localhost:3000/auth/verify?token=abc" in msg for msg in logs)


async def test_production_mode_calls_resend(monkeypatch) -> None:
    """Verify that when dev_mode is False, we call the Resend client."""
    monkeypatch.setenv("HANGAR_DEV_MODE", "0")
    monkeypatch.setenv("HANGAR_RESEND_API_KEY", "re_fake")
    from app.core.config import get_settings
    get_settings.cache_clear()

    sent_payloads: list[dict] = []

    class _FakeEmails:
        @staticmethod
        def send(payload):
            sent_payloads.append(payload)
            return {"id": "fake-message-id"}

    class _FakeResend:
        emails = _FakeEmails()

    import app.services.mailer as mailer
    monkeypatch.setattr(mailer, "_resend_client", lambda: _FakeResend)

    await send_magic_link_email(
        to="u@example.com",
        verify_url="http://localhost:3000/auth/verify?token=abc",
    )

    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["to"] == ["u@example.com"]
    assert "Sign in to Hangar" in payload["subject"]
    assert "abc" in payload["html"]
```

- [ ] **Step 2: Implement**

```python
# backend/app/services/__init__.py
```

```python
# backend/app/services/mailer.py
"""Email delivery via Resend, with dev-mode log fallback."""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_MAGIC_LINK_SUBJECT = "Sign in to Hangar"

_MAGIC_LINK_HTML = """<!doctype html>
<html>
  <body style="font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background:#070b10; color:#cfd4dc; padding:48px 24px;">
    <div style="max-width:480px;margin:0 auto;">
      <h1 style="color:#fff;font-size:22px;letter-spacing:-0.01em;">◈ Sign in to Hangar</h1>
      <p style="line-height:1.5;color:#8ba1bd;">Click the button below to sign in. The link expires in 15 minutes and can only be used once.</p>
      <p style="margin:32px 0;">
        <a href="{verify_url}" style="display:inline-block;background:#5cc8a4;color:#070b10;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">Sign in</a>
      </p>
      <p style="color:#5e7088;font-size:12px;">If the button doesn't work, paste this link: {verify_url}</p>
      <p style="color:#5e7088;font-size:12px;">If you didn't request this, ignore it.</p>
    </div>
  </body>
</html>"""


def _resend_client() -> Any:
    """Return the resend module. Kept as a function so tests can patch."""
    import resend

    resend.api_key = get_settings().resend_api_key
    return resend


async def send_magic_link_email(*, to: str, verify_url: str) -> None:
    settings = get_settings()
    if settings.dev_mode:
        logger.info(
            "DEV MAGIC LINK → to=%s verify_url=%s", to, verify_url
        )
        return

    client = _resend_client()
    payload = {
        "from": "Hangar <noreply@hangar.dev>",
        "to": [to],
        "subject": _MAGIC_LINK_SUBJECT,
        "html": _MAGIC_LINK_HTML.format(verify_url=verify_url),
    }
    # Resend SDK is sync; we call it synchronously from async context.
    # Acceptable for an outbound call that only runs on magic-link request.
    client.emails.send(payload)
```

- [ ] **Step 3: Run**

```bash
uv run pytest tests/test_mailer.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/mailer.py backend/tests/test_mailer.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): mailer — Resend delivery with HANGAR_DEV_MODE log fallback

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.4 — Login service (issue + verify + first-login bootstrap)

**Files:**
- Create: `backend/app/services/login.py`
- Test in `test_auth_verify.py` (next task)

- [ ] **Step 1: Write the service**

```python
# backend/app/services/login.py
"""Magic-link token issuance and verification + first-login workspace bootstrap."""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import generate_dek, wrap_dek
from app.core.errors import UnauthorizedError, ValidationError
from app.core.session import SessionPayload, create_session
from app.core.ulid import new_ulid
from app.models import MagicLinkToken, User, Workspace, WorkspaceKey, WorkspaceMember

_MAGIC_LINK_TTL_MINUTES = 15
_SLUG_RE = re.compile(r"[^a-z0-9-]")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def issue_magic_link(session: AsyncSession, *, email: str) -> str:
    """Create a magic-link token for `email` and return the RAW token (caller sends it in URL)."""
    raw = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(UTC) + timedelta(minutes=_MAGIC_LINK_TTL_MINUTES)

    session.add(MagicLinkToken(
        id=new_ulid(),
        email=email.strip().lower(),
        token_hash=token_hash,
        expires_at=expires_at,
    ))
    await session.flush()
    return raw


def _derive_workspace_slug(email: str) -> str:
    """Deterministic default-workspace slug from email local-part."""
    local = email.split("@", 1)[0].lower()
    slug = _SLUG_RE.sub("-", local)[:20].strip("-")
    if not slug:
        slug = "ws"
    return slug


async def _unique_slug(session: AsyncSession, desired: str) -> str:
    """Append -2, -3, ... if `desired` is taken."""
    slug = desired
    suffix = 1
    while True:
        result = await session.execute(select(Workspace.id).where(Workspace.slug == slug))
        if result.first() is None:
            return slug
        suffix += 1
        slug = f"{desired}-{suffix}"
        if len(slug) > 50:
            slug = slug[:50]


async def verify_magic_link(session: AsyncSession, *, raw_token: str) -> str:
    """Consume a raw magic-link token and return a session_id (creating user/workspace on first login)."""
    if not raw_token or len(raw_token) < 20:
        raise ValidationError(detail="invalid token")

    token_hash = _hash_token(raw_token)
    result = await session.execute(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise UnauthorizedError(detail="invalid or already-used link")
    if token.consumed_at is not None:
        raise UnauthorizedError(detail="link already used")
    if token.expires_at < datetime.now(UTC):
        raise UnauthorizedError(detail="link expired")

    email = token.email

    # Find or create user
    user_result = await session.execute(select(User).where(User.email == email))
    user = user_result.scalar_one_or_none()
    first_login = user is None
    if first_login:
        user = User(id=new_ulid(), email=email)
        session.add(user)
        await session.flush()

        # Create default workspace
        desired_slug = _derive_workspace_slug(email)
        slug = await _unique_slug(session, desired_slug)
        workspace = Workspace(
            id=new_ulid(),
            slug=slug,
            name=desired_slug.replace("-", " ").title() or "Default",
            owner_id=user.id,
        )
        session.add(workspace)
        await session.flush()

        # Owner membership
        session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))

        # DEK + wrap
        dek = generate_dek()
        wrapped = wrap_dek(dek, master_key_b64=get_settings().master_key)
        session.add(WorkspaceKey(workspace_id=workspace.id, dek_ciphertext=wrapped))
        await session.flush()
    else:
        # Find this user's first workspace (they may have more later)
        ws_result = await session.execute(
            select(Workspace).where(Workspace.owner_id == user.id).limit(1)
        )
        workspace = ws_result.scalar_one_or_none()
        if workspace is None:
            raise UnauthorizedError(detail="user has no workspace")

    # Mark token consumed
    token.consumed_at = datetime.now(UTC)
    await session.flush()

    # Create session
    session_id = await create_session(
        SessionPayload(user_id=user.id, workspace_id=workspace.id),
        ttl_seconds=get_settings().session_max_age,
    )
    return session_id
```

- [ ] **Step 2: Ruff + mypy sanity**

```bash
uv run ruff check .
uv run mypy app tests
```

No tests yet — both must pass on the new file alone.

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/login.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): login service — issue + verify magic links, first-login bootstrap

- issue_magic_link: generate 32-byte url-safe token, hash SHA-256,
  store hash + 15min expiry in magic_link_tokens.
- verify_magic_link: look up by hash, check expiry + consumed, mark
  consumed, create user+workspace+workspace_keys DEK on first login,
  return a Redis session_id.
- _derive_workspace_slug: email local-part → [a-z0-9-]{1,20}
- _unique_slug: -2, -3, ... suffix on collision.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.5 — Session middleware

**Files:**
- Create: `backend/app/core/middleware.py`

The middleware reads `hangar_session` cookie, looks up the session in Redis, and populates `request.state.user_id` / `request.state.workspace_id` plus sets `current_actor` and `current_workspace_id` contextvars for the request lifecycle.

- [ ] **Step 1: Implement**

```python
# backend/app/core/middleware.py
"""FastAPI middleware: session cookie → request.state + audit contextvars."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.audit import current_actor, current_workspace_id
from app.core.config import get_settings
from app.core.session import get_session

SESSION_COOKIE_NAME = "hangar_session"


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        actor_token = None
        workspace_token = None

        if session_id:
            payload = await get_session(session_id)
            if payload is not None:
                request.state.user_id = payload.user_id
                request.state.workspace_id = payload.workspace_id
                actor_token = current_actor.set(f"ui:{payload.user_id}")
                workspace_token = current_workspace_id.set(payload.workspace_id)

        try:
            return await call_next(request)
        finally:
            if actor_token is not None:
                current_actor.reset(actor_token)
            if workspace_token is not None:
                current_workspace_id.reset(workspace_token)


def install_session_middleware(app) -> None:  # type: ignore[no-untyped-def]
    from fastapi import FastAPI  # noqa: F401 — for type context
    app.add_middleware(SessionMiddleware)


def session_cookie_attrs() -> dict[str, object]:
    s = get_settings()
    return {
        "key": SESSION_COOKIE_NAME,
        "max_age": s.session_max_age,
        "httponly": True,
        "secure": not s.dev_mode,
        "samesite": "lax",
        "domain": s.cookie_domain if s.cookie_domain != "localhost" else None,
        "path": "/",
    }
```

- [ ] **Step 2: Ruff + mypy**

```bash
uv run ruff check .
uv run mypy app tests
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/middleware.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): SessionMiddleware reads hangar_session cookie + sets audit ctx

- request.state.user_id / workspace_id populated for authenticated requests
- current_actor / current_workspace_id contextvars set for the request
  lifecycle (audit listener picks them up automatically)
- session_cookie_attrs(): centralised cookie flags (httponly, SameSite=Lax,
  Secure in prod, domain from settings)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3.6 — Auth router (3 endpoints) + test

**Files:**
- Create: `backend/app/api/__init__.py` (empty)
- Create: `backend/app/api/v1/__init__.py` (empty)
- Create: `backend/app/api/v1/auth.py`
- Create: `backend/app/schemas/__init__.py` (empty)
- Create: `backend/app/schemas/auth.py`
- Modify: `backend/app/main.py` (mount router + install middleware + install audit listener at startup)
- Create: `backend/tests/test_auth_magic_link.py`
- Create: `backend/tests/test_auth_verify.py`

- [ ] **Step 1: Write the schemas**

```python
# backend/app/schemas/__init__.py
```

```python
# backend/app/schemas/auth.py
from pydantic import BaseModel, EmailStr


class MagicLinkRequest(BaseModel):
    email: EmailStr


class MagicLinkAccepted(BaseModel):
    status: str = "accepted"
```

- [ ] **Step 2: Write the router**

```python
# backend/app/api/__init__.py
```

```python
# backend/app/api/v1/__init__.py
```

```python
# backend/app/api/v1/auth.py
"""Auth routes: magic-link request + verify + logout."""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import RateLimitedError, UnauthorizedError
from app.core.middleware import SESSION_COOKIE_NAME, session_cookie_attrs
from app.core.rate_limit import check_and_consume
from app.core.session import delete_session
from app.schemas.auth import MagicLinkAccepted, MagicLinkRequest
from app.services.login import issue_magic_link, verify_magic_link
from app.services.mailer import send_magic_link_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/magic-link", status_code=202, response_model=MagicLinkAccepted)
async def request_magic_link(
    body: MagicLinkRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> MagicLinkAccepted:
    email = body.email.lower()

    # Rate limit: 3/hour per email, 10/hour per IP
    ip = request.client.host if request.client else "unknown"
    email_key = f"rl:auth:email:{email}"
    ip_key = f"rl:auth:ip:{ip}"

    email_ok, retry_email = await check_and_consume(email_key, capacity=3, refill_rate=3 / 3600)
    ip_ok, retry_ip = await check_and_consume(ip_key, capacity=10, refill_rate=10 / 3600)
    if not email_ok:
        raise RateLimitedError(detail="too many requests for this email", retry_after_s=retry_email)
    if not ip_ok:
        raise RateLimitedError(detail="too many requests from this IP", retry_after_s=retry_ip)

    # Always respond 202 (no user enumeration) — issue the link anyway,
    # even if we have no users for this address yet (first-login bootstrap
    # runs on verify).
    raw_token = await issue_magic_link(db, email=email)
    await db.commit()

    verify_url = f"{get_settings().base_url}/auth/verify?token={raw_token}"
    await send_magic_link_email(to=email, verify_url=verify_url)

    return MagicLinkAccepted()


@router.get("/verify")
async def verify(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    session_id = await verify_magic_link(db, raw_token=token)
    await db.commit()
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        value=session_id,
        **session_cookie_attrs(),  # type: ignore[arg-type]
    )
    return response


@router.post("/logout")
async def logout(
    hangar_session: str | None = Cookie(default=None),
) -> Response:
    if hangar_session:
        await delete_session(hangar_session)
    resp = Response(status_code=204)
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp
```

- [ ] **Step 3: Wire main.py**

```python
# backend/app/main.py
from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.core.audit import install_audit_listener
from app.core.middleware import install_session_middleware
from app.core.problem import install_problem_handler

app = FastAPI(title="Hangar", version="0.1.0")

install_problem_handler(app)
install_session_middleware(app)
install_audit_listener()

app.include_router(auth_router)


@app.get("/api/v1/healthz")
async def healthz() -> dict[str, object]:
    return {"ok": True, "version": app.version, "db": "unknown", "redis": "unknown"}
```

- [ ] **Step 4: Write the magic-link request test**

```python
# backend/tests/test_auth_magic_link.py
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

pytestmark = pytest.mark.integration


async def test_magic_link_accepts_valid_email(monkeypatch) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/magic-link", json={"email": "u@example.com"})
    assert resp.status_code == 202
    assert resp.json() == {"status": "accepted"}


async def test_magic_link_rejects_malformed_email() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/magic-link", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_magic_link_is_case_insensitive_for_email() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.post("/api/v1/auth/magic-link", json={"email": "MixedCase@Example.COM"})
    assert r1.status_code == 202
```

- [ ] **Step 5: Write the verify test**

```python
# backend/tests/test_auth_verify.py
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import Workspace, WorkspaceKey, WorkspaceMember
from app.services.login import issue_magic_link

pytestmark = pytest.mark.integration


async def test_verify_first_login_creates_user_workspace_and_dek(
    session: AsyncSession, monkeypatch,
) -> None:
    monkeypatch.setenv("HANGAR_DEV_MODE", "1")
    from app.core.config import get_settings
    get_settings.cache_clear()

    # Seed a magic-link token the way POST /auth/magic-link would
    raw_token = await issue_magic_link(session, email="new-user@example.com")
    await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
    ) as c:
        resp = await c.get(f"/api/v1/auth/verify?token={raw_token}")

    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    assert "hangar_session" in resp.headers.get("set-cookie", "")

    # Verify the bootstrap side effects
    ws = (await session.execute(
        select(Workspace).where(Workspace.name.icontains("New User") | Workspace.slug.icontains("new-user"))
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
    from datetime import UTC, datetime, timedelta
    import hashlib
    import secrets as _secrets
    from app.core.ulid import new_ulid
    from app.models import MagicLinkToken

    raw = _secrets.token_urlsafe(32)
    token = MagicLinkToken(
        id=new_ulid(), email="expired@example.com",
        token_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(token)
    await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get(f"/api/v1/auth/verify?token={raw}")
    assert resp.status_code == 401


async def test_verify_rejects_reused_token(session: AsyncSession) -> None:
    raw = await issue_magic_link(session, email="reuse@example.com")
    await session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
    ) as c:
        r1 = await c.get(f"/api/v1/auth/verify?token={raw}")
        r2 = await c.get(f"/api/v1/auth/verify?token={raw}")

    assert r1.status_code == 303
    assert r2.status_code == 401


async def test_logout_clears_cookie() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.post("/api/v1/auth/logout", cookies={"hangar_session": "01FAKE00000000000000000000"})
    assert resp.status_code == 204
    assert 'hangar_session=""' in resp.headers.get("set-cookie", "") or "hangar_session=;" in resp.headers.get("set-cookie", "")
```

- [ ] **Step 6: Collect + (CI) run**

```bash
uv run pytest tests/test_auth_magic_link.py tests/test_auth_verify.py --collect-only -q
uv run ruff check . && uv run mypy app tests
```

CI will actually run the integration tests. Locally, collect-only is enough.

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/ backend/app/schemas/ backend/app/main.py backend/tests/test_auth_magic_link.py backend/tests/test_auth_verify.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): auth router — POST /auth/magic-link, GET /auth/verify, POST /auth/logout

- POST /auth/magic-link: always 202, rate-limited (3/hr per email,
  10/hr per IP via Redis-Lua), issues token + sends email (or logs in
  dev mode), no user enumeration.
- GET /auth/verify?token=: consumes token, bootstraps user+workspace+
  workspace_keys DEK on first login, sets hangar_session cookie
  (httponly, Secure in prod, SameSite=Lax, 30d), 303 redirect to /.
- POST /auth/logout: deletes session + clears cookie, 204.

main.py now wires: problem handler, session middleware, audit listener
(idempotent), and mounts the auth router.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 3 complete when

- [ ] `/api/v1/auth/magic-link` accepts a valid email and returns 202 with `{"status":"accepted"}`.
- [ ] `/api/v1/auth/verify?token=X` on first-login creates user + workspace + workspace_members + workspace_keys (wrapped DEK) and sets the session cookie.
- [ ] Re-using an already-consumed magic link returns 401.
- [ ] Expired magic link returns 401.
- [ ] `/api/v1/auth/logout` clears the cookie and returns 204.
- [ ] Rate-limit triggers 429 with `Retry-After` header after 3/email or 10/IP per hour.
- [ ] HangarError → Problem+JSON for every auth endpoint.
- [ ] All Phase 2 tests still collect + CI green for Phase 3 integration tests.
- [ ] 6 commits on main (3.1–3.6) with exact subject lines.

Phase 4 (workspaces + `/me`) depends on session cookie + contextvars being set for every request.
