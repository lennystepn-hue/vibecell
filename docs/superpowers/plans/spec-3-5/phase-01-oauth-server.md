# Phase 1 — OAuth 2.1 Authorization Server

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Ship a spec-compliant OAuth 2.1 authorization server on the existing FastAPI backend. By end of phase, a curl-driven flow can: discover metadata → dynamically register a client → authorize → exchange code for tokens → refresh → revoke. No MCP endpoint yet (Phase 2), no UI yet (Phase 3). The consent step in this phase returns plain JSON — the branded Vue page lands in Phase 3.

**Architecture:** New package `backend/app/oauth/` with 4 files: `models.py` (SQLAlchemy tables), `discovery.py` (.well-known endpoints), `server.py` (register/authorize/token/revoke endpoints), `tokens.py` (JWT issue + verify + JTI blacklist). One Alembic migration `0005_oauth.py` for the 4 new tables. Endpoints mounted on the existing app at `/.well-known/*` and `/oauth/*`.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Pydantic v2, `pyjwt` for JWTs, `itsdangerous` for constant-time compare, Redis for JTI blacklist + rate-limits (already wired).

**Prerequisite:** Backend tests green at HEAD. Migration head is `0004`.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── oauth/
│   │   ├── __init__.py
│   │   ├── models.py              # OAuthClient, AuthCode, AccessToken, RefreshToken ORM tables
│   │   ├── schemas.py             # Pydantic request/response types
│   │   ├── tokens.py              # JWT sign/verify, opaque refresh-token gen, JTI blacklist
│   │   ├── discovery.py           # .well-known metadata endpoints
│   │   ├── server.py              # register/authorize/token/revoke endpoints
│   │   └── consent.py             # consent-state helper (render-neutral; Phase 3 adds the Vue page)
│   ├── core/
│   │   └── config.py              # (modify) add OAUTH_JWT_SECRET, OAUTH_TOKEN_TTL, OAUTH_REFRESH_TTL
│   └── main.py                    # (modify) mount oauth.router + discovery.router
├── alembic/versions/
│   └── 0005_oauth.py              # migration for 4 tables
└── tests/
    ├── test_oauth_models.py
    ├── test_oauth_tokens.py
    ├── test_oauth_discovery.py
    ├── test_oauth_register.py
    ├── test_oauth_authorize.py
    ├── test_oauth_token.py
    └── test_oauth_revoke.py
```

---

## Task 1.1 — Config extension

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Extend `Settings` class**

```python
# backend/app/core/config.py (additions inside class Settings)
    OAUTH_JWT_SECRET: str = Field(
        description="HMAC-SHA256 signing secret for OAuth access tokens. Must be ≥ 64 chars.",
        min_length=64,
    )
    OAUTH_ACCESS_TOKEN_TTL_SECONDS: int = 3600        # 1 hour
    OAUTH_REFRESH_TOKEN_TTL_SECONDS: int = 30 * 86400 # 30 days
    OAUTH_AUTH_CODE_TTL_SECONDS: int = 60
    OAUTH_MAX_CLIENTS_PER_USER: int = 50
    OAUTH_DCR_ORPHAN_TTL_HOURS: int = 24
```

- [ ] **Step 2: Add to `.env.example`**

```dotenv
# OAuth 2.1 — Remote MCP Server (Spec 3.5)
OAUTH_JWT_SECRET=replace-with-openssl-rand-hex-64-or-longer-pls
```

- [ ] **Step 3: Run existing test suite**

Run: `cd backend && uv run pytest -q`
Expected: All green (unchanged behavior).

- [ ] **Step 4: Commit**

```bash
git add backend/app/core/config.py backend/.env.example
git commit -m "feat(config): add OAuth 2.1 settings for Spec 3.5"
```

---

## Task 1.2 — Database models

**Files:**
- Create: `backend/app/oauth/__init__.py`
- Create: `backend/app/oauth/models.py`
- Create: `backend/tests/test_oauth_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_models.py
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.oauth.models import (
    OAuthAccessToken,
    OAuthAuthCode,
    OAuthClient,
    OAuthRefreshToken,
)


async def test_oauth_client_insert_roundtrip(async_session) -> None:
    client = OAuthClient(
        id="01OAC",
        client_id="dyn_client_1",
        client_name="Claude Desktop",
        redirect_uris=["http://127.0.0.1:12345/callback"],
        scope="vibecell:tools",
    )
    async_session.add(client)
    await async_session.flush()
    got = (await async_session.execute(select(OAuthClient).where(OAuthClient.client_id == "dyn_client_1"))).scalar_one()
    assert got.client_name == "Claude Desktop"
    assert got.revoked_at is None
    assert got.redirect_uris == ["http://127.0.0.1:12345/callback"]


async def test_auth_code_expires_at_default(async_session) -> None:
    code = OAuthAuthCode(
        id="01AUT",
        code="c_abc",
        client_id="dyn_client_1",
        user_id="01USR",
        workspace_id="01WSP",
        redirect_uri="http://127.0.0.1:12345/callback",
        code_challenge="xyz",
        scope="vibecell:tools",
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=60),
    )
    async_session.add(code)
    await async_session.flush()
    assert code.consumed_at is None


async def test_refresh_token_hash_unique_constraint(async_session) -> None:
    from sqlalchemy.exc import IntegrityError
    t1 = OAuthRefreshToken(
        id="01RT1",
        token_hash="sha_same",
        client_id="dyn_client_1",
        user_id="01USR",
        workspace_id="01WSP",
        scope="vibecell:tools",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    t2 = OAuthRefreshToken(
        id="01RT2",
        token_hash="sha_same",  # duplicate hash
        client_id="dyn_client_1",
        user_id="01USR",
        workspace_id="01WSP",
        scope="vibecell:tools",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    async_session.add_all([t1, t2])
    with pytest.raises(IntegrityError):
        await async_session.flush()


async def test_access_token_jti_indexed(async_session) -> None:
    tok = OAuthAccessToken(
        id="01AT1",
        jti="jti_abc",
        client_id="dyn_client_1",
        user_id="01USR",
        workspace_id="01WSP",
        scope="vibecell:tools",
        issued_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    async_session.add(tok)
    await async_session.flush()
    got = (await async_session.execute(select(OAuthAccessToken).where(OAuthAccessToken.jti == "jti_abc"))).scalar_one()
    assert got.revoked_at is None
```

- [ ] **Step 2: Write the implementation**

```python
# backend/app/oauth/__init__.py  (empty file)
```

```python
# backend/app/oauth/models.py
"""SQLAlchemy ORM models for OAuth 2.1 authorization server.

See docs/superpowers/specs/2026-04-20-spec-3-5-remote-mcp-oauth-design.md.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)                 # ULID
    client_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(255))
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(String))
    scope: Mapped[str] = mapped_column(String(255), default="vibecell:tools")
    registered_by_user_id: Mapped[str | None] = mapped_column(String(26), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAuthCode(Base):
    __tablename__ = "oauth_auth_codes"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id"))
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id"))
    redirect_uri: Mapped[str] = mapped_column(String(500))
    code_challenge: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthAccessToken(Base):
    __tablename__ = "oauth_access_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    jti: Mapped[str] = mapped_column(String(26), unique=True, index=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id"), index=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id"), index=True)
    scope: Mapped[str] = mapped_column(String(255))
    issued_from_refresh_family: Mapped[str | None] = mapped_column(String(26), index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthRefreshToken(Base):
    __tablename__ = "oauth_refresh_tokens"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)   # sha256 hex
    family_id: Mapped[str] = mapped_column(String(26), index=True)                 # groups rotations
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("oauth_clients.client_id"), index=True)
    user_id: Mapped[str] = mapped_column(String(26), ForeignKey("users.id"))
    workspace_id: Mapped[str] = mapped_column(String(26), ForeignKey("workspaces.id"), index=True)
    scope: Mapped[str] = mapped_column(String(255))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # single-use rotation
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_refresh_client_user", "client_id", "user_id"),
    )
```

- [ ] **Step 3: Run the test (expect FAIL — no table yet)**

Run: `cd backend && uv run pytest tests/test_oauth_models.py -q`
Expected: FAIL — `relation "oauth_clients" does not exist`. This is fine; Task 1.3 adds the migration.

- [ ] **Step 4: Commit**

```bash
git add backend/app/oauth/__init__.py backend/app/oauth/models.py backend/tests/test_oauth_models.py
git commit -m "feat(oauth): add ORM models for OAuth clients, codes, access+refresh tokens"
```

---

## Task 1.3 — Alembic migration `0005_oauth`

**Files:**
- Create: `backend/alembic/versions/0005_oauth.py`

- [ ] **Step 1: Generate skeleton**

Run: `cd backend && uv run alembic revision -m "oauth clients codes access refresh"`
Rename the created file to `0005_oauth.py`.

- [ ] **Step 2: Replace body**

```python
# backend/alembic/versions/0005_oauth.py
"""oauth clients codes access refresh

Revision ID: 0005_oauth
Revises: 0004_cli_devices
Create Date: 2026-04-20 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_oauth"
down_revision = "0004_cli_devices"  # update to actual prior revision id
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False, unique=True),
        sa.Column("client_name", sa.String(255)),
        sa.Column("redirect_uris", sa.ARRAY(sa.String), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False, server_default="vibecell:tools"),
        sa.Column("registered_by_user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_clients_client_id", "oauth_clients", ["client_id"])
    op.create_index("ix_oauth_clients_registered_by_user_id", "oauth_clients", ["registered_by_user_id"])

    op.create_table(
        "oauth_auth_codes",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_auth_codes_code", "oauth_auth_codes", ["code"])

    op.create_table(
        "oauth_access_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("jti", sa.String(26), nullable=False, unique=True),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("issued_from_refresh_family", sa.String(26)),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_access_tokens_jti", "oauth_access_tokens", ["jti"])
    op.create_index("ix_oauth_access_tokens_client_id", "oauth_access_tokens", ["client_id"])
    op.create_index("ix_oauth_access_tokens_workspace_id", "oauth_access_tokens", ["workspace_id"])
    op.create_index("ix_oauth_access_tokens_family", "oauth_access_tokens", ["issued_from_refresh_family"])

    op.create_table(
        "oauth_refresh_tokens",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("family_id", sa.String(26), nullable=False),
        sa.Column("client_id", sa.String(64), sa.ForeignKey("oauth_clients.client_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(26), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(26), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scope", sa.String(255), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_oauth_refresh_tokens_token_hash", "oauth_refresh_tokens", ["token_hash"])
    op.create_index("ix_oauth_refresh_tokens_family", "oauth_refresh_tokens", ["family_id"])
    op.create_index("ix_refresh_client_user", "oauth_refresh_tokens", ["client_id", "user_id"])


def downgrade() -> None:
    op.drop_table("oauth_refresh_tokens")
    op.drop_table("oauth_access_tokens")
    op.drop_table("oauth_auth_codes")
    op.drop_table("oauth_clients")
```

> **Important:** update `down_revision` to match the actual latest migration id. Check with `uv run alembic heads` first.

- [ ] **Step 3: Apply migration and rerun model tests**

Run:
```bash
cd backend && uv run alembic upgrade head
cd backend && uv run pytest tests/test_oauth_models.py -v
```
Expected: All 4 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/0005_oauth.py
git commit -m "feat(db): migration 0005 — oauth clients, auth codes, access + refresh tokens"
```

---

## Task 1.4 — Token issuer (JWT + opaque refresh + JTI blacklist)

**Files:**
- Create: `backend/app/oauth/tokens.py`
- Create: `backend/tests/test_oauth_tokens.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_tokens.py
from datetime import datetime, timedelta, timezone

import pytest

from app.oauth.tokens import (
    JTIBlacklist,
    OAuthTokenClaims,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
    verify_access_token,
)


def test_issue_and_verify_roundtrip() -> None:
    claims = OAuthTokenClaims(
        sub="01USR",
        client_id="dyn_c",
        workspace_id="01WSP",
        scope="vibecell:tools",
    )
    jwt_str, jti = issue_access_token(claims)
    decoded = verify_access_token(jwt_str)
    assert decoded.sub == "01USR"
    assert decoded.client_id == "dyn_c"
    assert decoded.workspace_id == "01WSP"
    assert decoded.jti == jti
    assert decoded.exp > decoded.iat


def test_verify_rejects_tampered_token() -> None:
    claims = OAuthTokenClaims(sub="01USR", client_id="c", workspace_id="w", scope="vibecell:tools")
    jwt_str, _ = issue_access_token(claims)
    tampered = jwt_str[:-4] + "aaaa"
    with pytest.raises(ValueError):
        verify_access_token(tampered)


def test_verify_rejects_expired_token(monkeypatch) -> None:
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "OAUTH_ACCESS_TOKEN_TTL_SECONDS", -1)
    claims = OAuthTokenClaims(sub="01USR", client_id="c", workspace_id="w", scope="vibecell:tools")
    jwt_str, _ = issue_access_token(claims)
    with pytest.raises(ValueError):
        verify_access_token(jwt_str)


def test_refresh_token_hash_stable() -> None:
    t = "rt_abc123"
    assert hash_refresh_token(t) == hash_refresh_token(t)
    assert hash_refresh_token(t) != hash_refresh_token("rt_xyz")


def test_issue_refresh_token_is_opaque_and_hashable() -> None:
    token = issue_refresh_token()
    assert token.startswith("rt_")
    assert len(token) >= 40
    h = hash_refresh_token(token)
    assert len(h) == 64  # sha256 hex


async def test_jti_blacklist_roundtrip() -> None:
    bl = JTIBlacklist()
    await bl.add("jti_123", ttl_seconds=60)
    assert await bl.is_revoked("jti_123")
    assert not await bl.is_revoked("jti_never_added")


async def test_jti_blacklist_ttl_expires(redis_client) -> None:
    bl = JTIBlacklist()
    await bl.add("jti_shortlived", ttl_seconds=1)
    import asyncio
    await asyncio.sleep(1.2)
    assert not await bl.is_revoked("jti_shortlived")
```

- [ ] **Step 2: Write the implementation**

```python
# backend/app/oauth/tokens.py
"""OAuth token issuance + verification + revocation blacklist.

Access tokens are JWTs (HS256). Refresh tokens are opaque 40-char strings
("rt_" + 32 random hex chars), stored as sha256 hashes.
"""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.ulid import new_ulid

_ISSUER = "https://vibecell.dev"
_AUDIENCE = "https://vibecell.dev/mcp"


@dataclass(frozen=True, slots=True)
class OAuthTokenClaims:
    sub: str
    client_id: str
    workspace_id: str
    scope: str
    jti: str | None = None
    iat: int = 0
    exp: int = 0


def issue_access_token(claims: OAuthTokenClaims) -> tuple[str, str]:
    """Return (jwt_string, jti). jti is the ULID used for revocation lookup."""
    s = get_settings()
    jti = new_ulid()
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "iss": _ISSUER,
        "aud": _AUDIENCE,
        "sub": claims.sub,
        "client_id": claims.client_id,
        "workspace_id": claims.workspace_id,
        "scope": claims.scope,
        "iat": now,
        "exp": now + s.OAUTH_ACCESS_TOKEN_TTL_SECONDS,
        "jti": jti,
    }
    encoded = jwt.encode(payload, s.OAUTH_JWT_SECRET, algorithm="HS256")
    return encoded, jti


def verify_access_token(token: str) -> OAuthTokenClaims:
    s = get_settings()
    try:
        payload = jwt.decode(
            token, s.OAUTH_JWT_SECRET, algorithms=["HS256"], audience=_AUDIENCE, issuer=_ISSUER,
        )
    except jwt.PyJWTError as e:
        raise ValueError("invalid_token") from e
    return OAuthTokenClaims(
        sub=payload["sub"],
        client_id=payload["client_id"],
        workspace_id=payload["workspace_id"],
        scope=payload["scope"],
        jti=payload["jti"],
        iat=payload["iat"],
        exp=payload["exp"],
    )


_REFRESH_PREFIX = "rt_"


def issue_refresh_token() -> str:
    return _REFRESH_PREFIX + secrets.token_hex(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


class JTIBlacklist:
    """Redis-backed set of revoked JTIs. Keys auto-expire at the token's exp."""

    _PREFIX = "oauth:revoked_jti:"

    async def add(self, jti: str, ttl_seconds: int) -> None:
        r = await get_redis()
        await r.set(f"{self._PREFIX}{jti}", "1", ex=max(1, ttl_seconds))

    async def is_revoked(self, jti: str) -> bool:
        r = await get_redis()
        return bool(await r.exists(f"{self._PREFIX}{jti}"))
```

- [ ] **Step 3: Run the test**

Run: `cd backend && uv run pytest tests/test_oauth_tokens.py -v`
Expected: All 7 PASS (requires Redis running — use `docker compose -f ops/docker-compose.dev.yml up -d redis`).

- [ ] **Step 4: Commit**

```bash
git add backend/app/oauth/tokens.py backend/tests/test_oauth_tokens.py
git commit -m "feat(oauth): JWT access tokens + opaque refresh tokens + JTI blacklist"
```

---

## Task 1.5 — Discovery endpoints

**Files:**
- Create: `backend/app/oauth/discovery.py`
- Modify: `backend/app/main.py` (mount)
- Create: `backend/tests/test_oauth_discovery.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_discovery.py
async def test_authorization_server_metadata(client) -> None:
    resp = await client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    body = resp.json()
    assert body["issuer"] == "https://vibecell.dev"
    assert body["authorization_endpoint"] == "https://vibecell.dev/oauth/authorize"
    assert body["token_endpoint"] == "https://vibecell.dev/oauth/token"
    assert body["revocation_endpoint"] == "https://vibecell.dev/oauth/revoke"
    assert body["registration_endpoint"] == "https://vibecell.dev/oauth/register"
    assert "authorization_code" in body["grant_types_supported"]
    assert "refresh_token" in body["grant_types_supported"]
    assert "S256" in body["code_challenge_methods_supported"]
    assert "vibecell:tools" in body["scopes_supported"]


async def test_protected_resource_metadata(client) -> None:
    resp = await client.get("/.well-known/oauth-protected-resource")
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == "https://vibecell.dev/mcp"
    assert body["authorization_servers"] == ["https://vibecell.dev"]
    assert body["bearer_methods_supported"] == ["header"]
```

- [ ] **Step 2: Write the implementation**

```python
# backend/app/oauth/discovery.py
"""OAuth / MCP discovery metadata endpoints (RFC 8414, RFC 9728)."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

_BASE = "https://vibecell.dev"


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server_metadata() -> dict:
    return {
        "issuer": _BASE,
        "authorization_endpoint": f"{_BASE}/oauth/authorize",
        "token_endpoint": f"{_BASE}/oauth/token",
        "revocation_endpoint": f"{_BASE}/oauth/revoke",
        "registration_endpoint": f"{_BASE}/oauth/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none", "client_secret_basic"],
        "scopes_supported": ["vibecell:tools"],
    }


@router.get("/.well-known/oauth-protected-resource")
async def protected_resource_metadata() -> dict:
    return {
        "resource": f"{_BASE}/mcp",
        "authorization_servers": [_BASE],
        "scopes_supported": ["vibecell:tools"],
        "bearer_methods_supported": ["header"],
    }
```

- [ ] **Step 3: Mount in `main.py`**

Add to `backend/app/main.py` (at top-level router registration):

```python
from app.oauth.discovery import router as oauth_discovery_router

app.include_router(oauth_discovery_router)
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_oauth_discovery.py -v`
Expected: Both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/oauth/discovery.py backend/app/main.py backend/tests/test_oauth_discovery.py
git commit -m "feat(oauth): discovery endpoints (/.well-known/oauth-authorization-server + oauth-protected-resource)"
```

---

## Task 1.6 — Pydantic schemas

**Files:**
- Create: `backend/app/oauth/schemas.py`

- [ ] **Step 1: Write the schemas**

```python
# backend/app/oauth/schemas.py
"""Pydantic request/response DTOs for OAuth endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl, field_validator

# ---- Dynamic Client Registration (RFC 7591) ----

class RegisterRequest(BaseModel):
    client_name: str | None = Field(None, max_length=255)
    redirect_uris: list[str] = Field(..., min_length=1, max_length=10)
    scope: str = "vibecell:tools"

    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: list[str]) -> list[str]:
        for uri in v:
            low = uri.lower()
            if low.startswith("https://"):
                continue
            if low.startswith("http://127.0.0.1") or low.startswith("http://localhost"):
                continue
            raise ValueError(f"redirect_uri must be HTTPS or loopback: {uri}")
        return v


class RegisterResponse(BaseModel):
    client_id: str
    client_id_issued_at: int
    client_name: str | None
    redirect_uris: list[str]
    scope: str
    token_endpoint_auth_method: str = "none"


# ---- Authorization (query params parsed by FastAPI) ----

class AuthorizeParams(BaseModel):
    response_type: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    state: str
    scope: str = "vibecell:tools"

    @field_validator("response_type")
    @classmethod
    def must_be_code(cls, v: str) -> str:
        if v != "code":
            raise ValueError("response_type must be 'code'")
        return v

    @field_validator("code_challenge_method")
    @classmethod
    def must_be_s256(cls, v: str) -> str:
        if v != "S256":
            raise ValueError("code_challenge_method must be 'S256'")
        return v


class GrantRequest(BaseModel):
    state: str
    workspace_id: str


# ---- Token ----

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str
```

- [ ] **Step 2: Commit (no tests — covered via endpoint tests)**

```bash
git add backend/app/oauth/schemas.py
git commit -m "feat(oauth): pydantic DTOs for register/authorize/token"
```

---

## Task 1.7 — Dynamic Client Registration endpoint

**Files:**
- Create: `backend/app/oauth/server.py` (first part)
- Create: `backend/tests/test_oauth_register.py`
- Modify: `backend/app/main.py` (mount)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_register.py
async def test_register_happy_path(client) -> None:
    resp = await client.post(
        "/oauth/register",
        json={
            "client_name": "Claude Desktop",
            "redirect_uris": ["http://127.0.0.1:12345/callback"],
            "scope": "vibecell:tools",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["client_id"].startswith("dyn_")
    assert body["client_name"] == "Claude Desktop"
    assert body["redirect_uris"] == ["http://127.0.0.1:12345/callback"]
    assert body["token_endpoint_auth_method"] == "none"
    assert isinstance(body["client_id_issued_at"], int)


async def test_register_rejects_http_non_loopback(client) -> None:
    resp = await client.post(
        "/oauth/register",
        json={
            "client_name": "Sketchy",
            "redirect_uris": ["http://evil.com/cb"],
            "scope": "vibecell:tools",
        },
    )
    assert resp.status_code == 422


async def test_register_accepts_https(client) -> None:
    resp = await client.post(
        "/oauth/register",
        json={
            "client_name": "Web",
            "redirect_uris": ["https://app.example.com/cb"],
            "scope": "vibecell:tools",
        },
    )
    assert resp.status_code == 201


async def test_register_rate_limit(client) -> None:
    # 11th request from same IP should 429.
    for i in range(10):
        resp = await client.post(
            "/oauth/register",
            json={"client_name": f"c{i}", "redirect_uris": ["http://127.0.0.1:1/cb"]},
        )
        assert resp.status_code == 201
    resp = await client.post(
        "/oauth/register",
        json={"client_name": "c11", "redirect_uris": ["http://127.0.0.1:1/cb"]},
    )
    assert resp.status_code == 429
```

- [ ] **Step 2: Write implementation (part 1 — register only)**

```python
# backend/app/oauth/server.py
"""OAuth 2.1 authorization-server endpoints.

- POST /oauth/register (RFC 7591 Dynamic Client Registration)
- GET  /oauth/authorize (user-facing; for Phase 1 returns JSON; Phase 3 renders Vue)
- POST /oauth/grant (internal: consent-submit)
- POST /oauth/token (code→token, refresh rotation)
- POST /oauth/revoke (RFC 7009)
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.ratelimit import enforce_rate_limit
from app.core.ulid import new_ulid
from app.oauth.models import OAuthClient
from app.oauth.schemas import RegisterRequest, RegisterResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    await enforce_rate_limit(f"oauth:register:{request.client.host}", max_per_minute=10)

    now = datetime.now(timezone.utc)
    client_id = "dyn_" + secrets.token_urlsafe(16)
    row = OAuthClient(
        id=new_ulid(),
        client_id=client_id,
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
        created_at=now,
    )
    db.add(row)
    await db.flush()

    return RegisterResponse(
        client_id=client_id,
        client_id_issued_at=int(now.timestamp()),
        client_name=body.client_name,
        redirect_uris=body.redirect_uris,
        scope=body.scope,
    )
```

- [ ] **Step 3: Mount router in `main.py`**

Add:
```python
from app.oauth.server import router as oauth_server_router
app.include_router(oauth_server_router)
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_oauth_register.py -v`
Expected: All 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/oauth/server.py backend/app/main.py backend/tests/test_oauth_register.py
git commit -m "feat(oauth): POST /oauth/register — dynamic client registration (RFC 7591)"
```

---

## Task 1.8 — Authorize endpoint (Phase 1 JSON-only; Phase 3 replaces with Vue)

**Files:**
- Modify: `backend/app/oauth/server.py` (add authorize + grant)
- Create: `backend/app/oauth/consent.py`
- Create: `backend/tests/test_oauth_authorize.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_authorize.py
async def test_authorize_requires_signin(client) -> None:
    # Unauth'd call → 302 redirect to /login
    resp = await client.get(
        "/oauth/authorize?response_type=code&client_id=dyn_x&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=xyz&scope=vibecell:tools",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"].startswith("/login?next=")


async def test_authorize_returns_consent_context(authed_client, registered_oauth_client) -> None:
    # Signed-in user → 200 with consent context JSON (Phase 3 turns this into HTML)
    cid = registered_oauth_client.client_id
    resp = await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=xyz&scope=vibecell:tools",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["client_id"] == cid
    assert body["client_name"] is not None
    assert isinstance(body["workspaces"], list)
    assert body["state"] == "xyz"


async def test_grant_issues_code(authed_client, registered_oauth_client, user_workspace) -> None:
    # POST /oauth/grant with state from an active authorize → 302 to redirect_uri with ?code=
    cid = registered_oauth_client.client_id
    get_resp = await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=s1&scope=vibecell:tools",
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


async def test_grant_invalid_workspace_rejected(authed_client, registered_oauth_client) -> None:
    cid = registered_oauth_client.client_id
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        "&code_challenge=abc&code_challenge_method=S256&state=s2&scope=vibecell:tools",
    )
    resp = await authed_client.post(
        "/oauth/grant",
        json={"state": "s2", "workspace_id": "01BADWORKSPACE"},
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Implement consent helper**

```python
# backend/app/oauth/consent.py
"""Ephemeral consent state — maps `state` → validated authorize params.

Stored in Redis (TTL 10min) so it survives sign-in-redirect roundtrips.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from app.core.redis import get_redis

_PREFIX = "oauth:consent:"
_TTL = 600  # 10 min


@dataclass(frozen=True, slots=True)
class ConsentState:
    client_id: str
    redirect_uri: str
    code_challenge: str
    scope: str
    state: str
    user_id: str   # filled in once signed in


async def store(cs: ConsentState) -> None:
    r = await get_redis()
    await r.set(f"{_PREFIX}{cs.state}", json.dumps(asdict(cs)), ex=_TTL)


async def fetch(state: str) -> ConsentState | None:
    r = await get_redis()
    raw = await r.get(f"{_PREFIX}{state}")
    if raw is None:
        return None
    return ConsentState(**json.loads(raw))


async def drop(state: str) -> None:
    r = await get_redis()
    await r.delete(f"{_PREFIX}{state}")
```

- [ ] **Step 3: Add authorize + grant to `server.py`**

Append to `backend/app/oauth/server.py`:

```python
from fastapi import Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from urllib.parse import quote

from app.api.v1.auth import require_user   # existing dependency that returns user or 401
from app.oauth import consent
from app.oauth.schemas import AuthorizeParams, GrantRequest
from app.oauth.models import OAuthAuthCode
from app.services.workspaces import WorkspaceService


@router.get("/authorize")
async def authorize(
    request: Request,
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(...),
    state: str = Query(...),
    scope: str = Query("vibecell:tools"),
    db: AsyncSession = Depends(get_db),
):
    # Validate params via pydantic model (raises 422 on invalid)
    AuthorizeParams(
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        state=state,
        scope=scope,
    )

    # Client exists & redirect_uri registered?
    row = (await db.execute(select(OAuthClient).where(OAuthClient.client_id == client_id, OAuthClient.revoked_at.is_(None)))).scalar_one_or_none()
    if not row:
        raise HTTPException(400, "invalid_client")
    if redirect_uri not in row.redirect_uris:
        raise HTTPException(400, "invalid_redirect_uri")

    # Rate limit
    await enforce_rate_limit(f"oauth:authorize:{request.client.host}", max_per_minute=30)

    # User signed in?
    session = request.scope.get("auth_user", None)
    if session is None:
        # Re-authorize after login using the full URL
        next_url = str(request.url)
        return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=302)

    # Stash consent state
    await consent.store(consent.ConsentState(
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        scope=scope,
        state=state,
        user_id=session.user_id,
    ))

    # Return consent context (Phase 3 replaces this with HTML/Vue render)
    ws_service = WorkspaceService(db)
    workspaces = await ws_service.list_for_user(session.user_id)
    return {
        "client_id": row.client_id,
        "client_name": row.client_name,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "workspaces": [{"id": w.id, "slug": w.slug, "name": w.name} for w in workspaces],
    }


@router.post("/grant")
async def grant(
    body: GrantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user = Depends(require_user),
):
    cs = await consent.fetch(body.state)
    if cs is None or cs.user_id != user.id:
        raise HTTPException(400, "invalid_state")

    # Verify the user is a member of the chosen workspace
    ws_service = WorkspaceService(db)
    workspaces = await ws_service.list_for_user(user.id)
    if body.workspace_id not in {w.id for w in workspaces}:
        raise HTTPException(403, "workspace_forbidden")

    # Issue auth code
    code = "c_" + secrets.token_urlsafe(24)
    now = datetime.now(timezone.utc)
    row = OAuthAuthCode(
        id=new_ulid(),
        code=code,
        client_id=cs.client_id,
        user_id=user.id,
        workspace_id=body.workspace_id,
        redirect_uri=cs.redirect_uri,
        code_challenge=cs.code_challenge,
        scope=cs.scope,
        expires_at=now + timedelta(seconds=get_settings().OAUTH_AUTH_CODE_TTL_SECONDS),
    )
    db.add(row)
    await db.flush()
    await consent.drop(body.state)

    # Redirect back to the client with the code
    sep = "&" if "?" in cs.redirect_uri else "?"
    return RedirectResponse(
        url=f"{cs.redirect_uri}{sep}code={code}&state={cs.state}", status_code=302,
    )


@router.post("/deny")
async def deny(body: GrantRequest, user = Depends(require_user)):
    cs = await consent.fetch(body.state)
    if cs is None or cs.user_id != user.id:
        raise HTTPException(400, "invalid_state")
    await consent.drop(body.state)
    sep = "&" if "?" in cs.redirect_uri else "?"
    return RedirectResponse(
        url=f"{cs.redirect_uri}{sep}error=access_denied&state={cs.state}", status_code=302,
    )
```

Also add the imports at top:

```python
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_oauth_authorize.py -v`
Expected: All 4 PASS.

- [ ] **Step 5: Add the fixtures**

`authed_client` and `user_workspace` are presumed to exist from Spec 1 phase-03 conftest (fail fast and add them if not). Spec-3.5-specific `registered_oauth_client` is new — add:

```python
# backend/tests/conftest.py (additions)
import pytest_asyncio

from app.oauth.models import OAuthClient
from app.core.ulid import new_ulid
from datetime import datetime, timezone


@pytest_asyncio.fixture
async def registered_oauth_client(async_session):
    row = OAuthClient(
        id=new_ulid(),
        client_id="dyn_" + new_ulid()[:16],
        client_name="Test Client",
        redirect_uris=["http://127.0.0.1:1/cb"],
        scope="vibecell:tools",
        created_at=datetime.now(timezone.utc),
    )
    async_session.add(row)
    await async_session.flush()
    yield row
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/oauth/server.py backend/app/oauth/consent.py backend/tests/test_oauth_authorize.py backend/tests/conftest.py
git commit -m "feat(oauth): /authorize + /grant + /deny endpoints (auth_code issuance + consent state)"
```

---

## Task 1.9 — Token endpoint (code→token + refresh rotation)

**Files:**
- Modify: `backend/app/oauth/server.py`
- Create: `backend/tests/test_oauth_token.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_token.py
import base64
import hashlib


def _pkce_pair() -> tuple[str, str]:
    verifier = "v" + "a" * 42   # 43 chars, letters only
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


async def test_token_code_exchange_happy_path(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]

    # authorize + grant to obtain a code
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s1&scope=vibecell:tools",
    )
    r = await authed_client.post(
        "/oauth/grant",
        json={"state": "s1", "workspace_id": user_workspace.id},
        follow_redirects=False,
    )
    loc = r.headers["location"]
    code = loc.split("code=")[1].split("&")[0]

    # exchange
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
    assert body["access_token"].count(".") == 2  # JWT
    assert body["refresh_token"].startswith("rt_")


async def test_token_rejects_wrong_pkce_verifier(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s2&scope=vibecell:tools",
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
    assert resp.json()["error"] == "invalid_grant"


async def test_token_code_single_use(client, authed_client, registered_oauth_client, user_workspace) -> None:
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s3&scope=vibecell:tools",
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
    assert again.json()["error"] == "invalid_grant"


async def test_refresh_token_rotation(client, authed_client, registered_oauth_client, user_workspace) -> None:
    # Obtain initial pair
    verifier, challenge = _pkce_pair()
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=s4&scope=vibecell:tools",
    )
    r = await authed_client.post("/oauth/grant", json={"state": "s4", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]
    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
        "client_id": cid, "code_verifier": verifier,
    })).json()
    rt = tok["refresh_token"]

    # Use refresh
    r2 = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert r2.status_code == 200
    new_pair = r2.json()
    assert new_pair["refresh_token"] != rt  # rotation
    assert new_pair["access_token"] != tok["access_token"]

    # Old refresh token must now fail
    r3 = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert r3.status_code == 400
    assert r3.json()["error"] == "invalid_grant"
```

- [ ] **Step 2: Implement token endpoint**

Append to `backend/app/oauth/server.py`:

```python
import base64
import hashlib
from fastapi import Form

from app.oauth.models import OAuthAccessToken, OAuthRefreshToken
from app.oauth.tokens import (
    OAuthTokenClaims,
    hash_refresh_token,
    issue_access_token,
    issue_refresh_token,
)


@router.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    code_verifier: str | None = Form(None),
    refresh_token: str | None = Form(None),
    client_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(f"oauth:token:{client_id}", max_per_minute=20)

    if grant_type == "authorization_code":
        return await _token_from_code(db, code, redirect_uri, code_verifier, client_id)
    if grant_type == "refresh_token":
        return await _token_from_refresh(db, refresh_token, client_id)
    raise HTTPException(400, detail={"error": "unsupported_grant_type"})


def _verify_pkce(verifier: str, challenge: str) -> bool:
    digest = hashlib.sha256(verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return secrets.compare_digest(expected, challenge)


async def _token_from_code(
    db: AsyncSession, code: str | None, redirect_uri: str | None,
    code_verifier: str | None, client_id: str,
):
    if not (code and redirect_uri and code_verifier):
        raise HTTPException(400, detail={"error": "invalid_request"})

    row = (await db.execute(
        select(OAuthAuthCode).where(OAuthAuthCode.code == code)
    )).scalar_one_or_none()
    if row is None or row.consumed_at is not None:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.client_id != client_id:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.redirect_uri != redirect_uri:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if not _verify_pkce(code_verifier, row.code_challenge):
        raise HTTPException(400, detail={"error": "invalid_grant"})

    now = datetime.now(timezone.utc)
    row.consumed_at = now
    s = get_settings()

    # Issue access token
    jwt_str, jti = issue_access_token(OAuthTokenClaims(
        sub=row.user_id, client_id=row.client_id, workspace_id=row.workspace_id, scope=row.scope,
    ))
    family_id = new_ulid()
    db.add(OAuthAccessToken(
        id=new_ulid(), jti=jti, client_id=row.client_id, user_id=row.user_id,
        workspace_id=row.workspace_id, scope=row.scope, issued_from_refresh_family=family_id,
        issued_at=now, expires_at=now + timedelta(seconds=s.OAUTH_ACCESS_TOKEN_TTL_SECONDS),
    ))

    # Issue refresh token (opaque, stored hashed)
    rt_value = issue_refresh_token()
    db.add(OAuthRefreshToken(
        id=new_ulid(), token_hash=hash_refresh_token(rt_value), family_id=family_id,
        client_id=row.client_id, user_id=row.user_id, workspace_id=row.workspace_id,
        scope=row.scope, issued_at=now,
        expires_at=now + timedelta(seconds=s.OAUTH_REFRESH_TOKEN_TTL_SECONDS),
    ))

    # Backfill registered_by_user_id + touch last_used_at on client
    client_row = (await db.execute(
        select(OAuthClient).where(OAuthClient.client_id == row.client_id)
    )).scalar_one()
    if client_row.registered_by_user_id is None:
        client_row.registered_by_user_id = row.user_id
    client_row.last_used_at = now

    await db.flush()

    return {
        "access_token": jwt_str,
        "token_type": "Bearer",
        "expires_in": s.OAUTH_ACCESS_TOKEN_TTL_SECONDS,
        "refresh_token": rt_value,
        "scope": row.scope,
    }


async def _token_from_refresh(db: AsyncSession, refresh_token: str | None, client_id: str):
    if not refresh_token:
        raise HTTPException(400, detail={"error": "invalid_request"})

    h = hash_refresh_token(refresh_token)
    row = (await db.execute(
        select(OAuthRefreshToken).where(OAuthRefreshToken.token_hash == h)
    )).scalar_one_or_none()
    if row is None or row.consumed_at is not None or row.revoked_at is not None:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.client_id != client_id:
        raise HTTPException(400, detail={"error": "invalid_grant"})
    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, detail={"error": "invalid_grant"})

    now = datetime.now(timezone.utc)
    row.consumed_at = now
    s = get_settings()

    # Issue new access
    jwt_str, jti = issue_access_token(OAuthTokenClaims(
        sub=row.user_id, client_id=row.client_id, workspace_id=row.workspace_id, scope=row.scope,
    ))
    db.add(OAuthAccessToken(
        id=new_ulid(), jti=jti, client_id=row.client_id, user_id=row.user_id,
        workspace_id=row.workspace_id, scope=row.scope, issued_from_refresh_family=row.family_id,
        issued_at=now, expires_at=now + timedelta(seconds=s.OAUTH_ACCESS_TOKEN_TTL_SECONDS),
    ))

    # Rotate refresh
    new_rt = issue_refresh_token()
    db.add(OAuthRefreshToken(
        id=new_ulid(), token_hash=hash_refresh_token(new_rt), family_id=row.family_id,
        client_id=row.client_id, user_id=row.user_id, workspace_id=row.workspace_id,
        scope=row.scope, issued_at=now,
        expires_at=now + timedelta(seconds=s.OAUTH_REFRESH_TOKEN_TTL_SECONDS),
    ))

    await db.flush()
    return {
        "access_token": jwt_str,
        "token_type": "Bearer",
        "expires_in": s.OAUTH_ACCESS_TOKEN_TTL_SECONDS,
        "refresh_token": new_rt,
        "scope": row.scope,
    }
```

- [ ] **Step 3: Run the tests**

Run: `cd backend && uv run pytest tests/test_oauth_token.py -v`
Expected: All 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/oauth/server.py backend/tests/test_oauth_token.py
git commit -m "feat(oauth): POST /oauth/token — code exchange + refresh rotation with PKCE verification"
```

---

## Task 1.10 — Revoke endpoint

**Files:**
- Modify: `backend/app/oauth/server.py`
- Create: `backend/tests/test_oauth_revoke.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_oauth_revoke.py
async def test_revoke_access_token_blacklists_jti(client, issued_token_pair) -> None:
    access = issued_token_pair["access_token"]
    resp = await client.post("/oauth/revoke", data={"token": access, "token_type_hint": "access_token"})
    assert resp.status_code == 200

    # Subsequent verification must fail via JTI blacklist
    from app.oauth.tokens import verify_access_token, JTIBlacklist
    claims = verify_access_token(access)
    assert await JTIBlacklist().is_revoked(claims.jti)


async def test_revoke_refresh_token_invalidates(client, issued_token_pair) -> None:
    rt = issued_token_pair["refresh_token"]
    resp = await client.post("/oauth/revoke", data={"token": rt, "token_type_hint": "refresh_token"})
    assert resp.status_code == 200

    # Try to use it → invalid_grant
    cid = issued_token_pair["client_id"]
    again = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": rt, "client_id": cid,
    })
    assert again.status_code == 400


async def test_revoke_unknown_token_returns_200(client) -> None:
    # RFC 7009 requires 200 for unknown tokens
    resp = await client.post("/oauth/revoke", data={"token": "rt_nonexistent", "token_type_hint": "refresh_token"})
    assert resp.status_code == 200
```

- [ ] **Step 2: Implement revoke**

Append to `backend/app/oauth/server.py`:

```python
from fastapi import Response
from app.oauth.tokens import JTIBlacklist, verify_access_token


@router.post("/revoke")
async def revoke(
    token: str = Form(...),
    token_type_hint: str = Form("access_token"),
    db: AsyncSession = Depends(get_db),
) -> Response:
    # RFC 7009: return 200 regardless of token validity
    try:
        if token_type_hint == "refresh_token":
            await _revoke_refresh(db, token)
        else:
            await _revoke_access(db, token)
    except Exception:  # noqa: BLE001 — intentional broad swallow per RFC
        pass
    return Response(status_code=200)


async def _revoke_access(db: AsyncSession, token: str) -> None:
    try:
        claims = verify_access_token(token)
    except ValueError:
        return
    ttl = max(1, claims.exp - int(datetime.now(timezone.utc).timestamp()))
    await JTIBlacklist().add(claims.jti, ttl_seconds=ttl)
    row = (await db.execute(
        select(OAuthAccessToken).where(OAuthAccessToken.jti == claims.jti)
    )).scalar_one_or_none()
    if row:
        row.revoked_at = datetime.now(timezone.utc)


async def _revoke_refresh(db: AsyncSession, token: str) -> None:
    h = hash_refresh_token(token)
    row = (await db.execute(
        select(OAuthRefreshToken).where(OAuthRefreshToken.token_hash == h)
    )).scalar_one_or_none()
    if row is None:
        return
    now = datetime.now(timezone.utc)
    row.revoked_at = now
    # Cascade: revoke all access tokens in same family still valid
    access_rows = (await db.execute(
        select(OAuthAccessToken).where(
            OAuthAccessToken.issued_from_refresh_family == row.family_id,
            OAuthAccessToken.revoked_at.is_(None),
            OAuthAccessToken.expires_at > now,
        )
    )).scalars()
    for ar in access_rows:
        ar.revoked_at = now
        ttl = max(1, int(ar.expires_at.timestamp()) - int(now.timestamp()))
        await JTIBlacklist().add(ar.jti, ttl_seconds=ttl)
```

- [ ] **Step 3: Add fixture `issued_token_pair` to `conftest.py`**

```python
# backend/tests/conftest.py (additions)
import pytest_asyncio


@pytest_asyncio.fixture
async def issued_token_pair(authed_client, client, registered_oauth_client, user_workspace):
    import base64, hashlib
    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    cid = registered_oauth_client.client_id
    redirect = registered_oauth_client.redirect_uris[0]

    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri={redirect}"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=fix&scope=vibecell:tools",
    )
    r = await authed_client.post("/oauth/grant", json={"state": "fix", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = r.headers["location"].split("code=")[1].split("&")[0]
    pair = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect,
        "client_id": cid, "code_verifier": verifier,
    })).json()
    pair["client_id"] = cid
    return pair
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && uv run pytest tests/test_oauth_revoke.py -v`
Expected: All 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/oauth/server.py backend/tests/test_oauth_revoke.py backend/tests/conftest.py
git commit -m "feat(oauth): POST /oauth/revoke — RFC 7009 revocation with JTI blacklist cascade"
```

---

## Task 1.11 — End-of-Phase integration test

**Files:**
- Create: `backend/tests/integration/test_oauth_full_flow.py`

- [ ] **Step 1: Write E2E test**

```python
# backend/tests/integration/test_oauth_full_flow.py
"""Full OAuth 2.1 spec flow against the live backend.
register → authorize → grant → token → refresh → revoke.
"""
import base64
import hashlib


async def test_full_oauth_lifecycle(client, authed_client, user_workspace) -> None:
    # 1. Discovery
    meta = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert meta["issuer"]

    # 2. Register
    reg = (await client.post("/oauth/register", json={
        "client_name": "e2e-test",
        "redirect_uris": ["http://127.0.0.1:1/cb"],
    })).json()
    cid = reg["client_id"]

    # 3. Authorize (signed-in user)
    verifier = "v" + "a" * 42
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    await authed_client.get(
        f"/oauth/authorize?response_type=code&client_id={cid}&redirect_uri=http://127.0.0.1:1/cb"
        f"&code_challenge={challenge}&code_challenge_method=S256&state=e2e&scope=vibecell:tools",
    )

    # 4. Grant
    grant_resp = await authed_client.post("/oauth/grant", json={"state": "e2e", "workspace_id": user_workspace.id}, follow_redirects=False)
    code = grant_resp.headers["location"].split("code=")[1].split("&")[0]

    # 5. Token
    tok = (await client.post("/oauth/token", data={
        "grant_type": "authorization_code", "code": code, "redirect_uri": "http://127.0.0.1:1/cb",
        "client_id": cid, "code_verifier": verifier,
    })).json()
    assert "access_token" in tok
    assert "refresh_token" in tok

    # 6. Refresh
    refresh_resp = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"], "client_id": cid,
    })
    new_tok = refresh_resp.json()
    assert new_tok["refresh_token"] != tok["refresh_token"]

    # 7. Revoke refresh
    await client.post("/oauth/revoke", data={"token": new_tok["refresh_token"], "token_type_hint": "refresh_token"})
    bad = await client.post("/oauth/token", data={
        "grant_type": "refresh_token", "refresh_token": new_tok["refresh_token"], "client_id": cid,
    })
    assert bad.status_code == 400
```

- [ ] **Step 2: Run**

Run: `cd backend && uv run pytest tests/integration/test_oauth_full_flow.py -v`
Expected: PASS.

- [ ] **Step 3: Phase-close commit**

```bash
git add backend/tests/integration/test_oauth_full_flow.py
git commit -m "test(oauth): E2E lifecycle — register → authorize → token → refresh → revoke"
```

---

## End of Phase 1 — Checklist

- [ ] All 7 OAuth test files pass: `uv run pytest tests/test_oauth_*.py tests/integration/test_oauth_full_flow.py -v`
- [ ] Coverage ≥ 85% on `backend/app/oauth/`: `uv run pytest --cov=app.oauth tests/test_oauth_* tests/integration/test_oauth_full_flow.py`
- [ ] Discovery returns spec-compliant JSON for both `.well-known/*` endpoints
- [ ] Rate-limit enforced on `/oauth/register` and `/oauth/token`
- [ ] PKCE S256 enforced; `plain` rejected
- [ ] Migration 0005 applied cleanly; `alembic downgrade` works
- [ ] No changes to existing auth / session / api routes (verify by running full `uv run pytest -q`)
- [ ] `backend/.env.example` updated

Proceed to Phase 2.
