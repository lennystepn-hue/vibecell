# Phase 2 — Core Utilities

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Build the shared infrastructure that every route + service will use — AES-256-GCM envelope crypto (workspace-scoped DEKs wrapped with the server master key), SQLAlchemy audit-log listener that captures every write, async Redis client, token-bucket rate-limiter, and a typed exception hierarchy that maps to RFC 7807 Problem Details.

**Architecture:** Each utility is a small focused module under `app/core/`. Crypto uses `cryptography`'s AEAD primitive (`AESGCM`) with 12-byte nonces. Audit listener lives in `app/core/audit.py` and registers on `AsyncSession`'s `after_flush` event, reading actor + workspace from context-vars set by auth middleware (to be added in Phase 3 — for now, tests set them manually). Redis client is a singleton wrapping `redis.asyncio.Redis`. Rate-limiter is a Redis Lua script for atomic token-bucket counting. Exceptions all inherit `HangarError(title, status, type)` and get mapped to Problem+JSON by a FastAPI exception handler (wired in Phase 3).

**Tech Stack:** `cryptography` 44.x, `redis[hiredis]` 5.x, `contextvars` stdlib, pytest integration tests against real Postgres + real Redis.

**Prerequisite:** Phase 1 complete (HEAD ≥ `320bfe6`). Models + DB module + conftest in place.

---

## File structure produced by this phase

```
backend/
├── app/
│   ├── core/
│   │   ├── (existing: __init__.py, config.py, db.py, ulid.py)
│   │   ├── crypto.py                   AES-256-GCM envelope crypto + DEK wrap/unwrap
│   │   ├── redis.py                    async Redis client singleton
│   │   ├── rate_limit.py               token-bucket via Redis Lua
│   │   ├── audit.py                    SQLAlchemy session listener + contextvars
│   │   └── errors.py                   HangarError hierarchy
│   └── (models/, main.py, etc. unchanged)
└── tests/
    ├── test_crypto.py
    ├── test_redis.py
    ├── test_rate_limit.py
    ├── test_audit.py
    └── test_errors.py
```

---

## Task 2.1 — Exception hierarchy

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_errors.py
from app.core.errors import (
    ConflictError,
    ForbiddenError,
    HangarError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


def test_hangar_error_base_has_fields() -> None:
    err = HangarError(title="Broken", status=418, type_="/errors/broken", detail="teapot")
    assert err.title == "Broken"
    assert err.status == 418
    assert err.type == "/errors/broken"
    assert err.detail == "teapot"


def test_hangar_error_to_problem_dict() -> None:
    err = HangarError(title="X", status=500, type_="/errors/x", detail="d")
    d = err.to_problem()
    assert d == {"type": "/errors/x", "title": "X", "status": 500, "detail": "d"}


def test_not_found_defaults() -> None:
    err = NotFoundError("project", "butlr")
    assert err.status == 404
    assert err.type == "/errors/not-found"
    assert "butlr" in err.detail
    assert "project" in err.detail


def test_conflict_defaults() -> None:
    err = ConflictError(detail="slug 'x' already exists")
    assert err.status == 409
    assert err.type == "/errors/conflict"


def test_unauthorized_defaults() -> None:
    err = UnauthorizedError()
    assert err.status == 401
    assert err.type == "/errors/unauthorized"


def test_forbidden_defaults() -> None:
    err = ForbiddenError(detail="not your workspace")
    assert err.status == 403
    assert err.type == "/errors/forbidden"


def test_validation_defaults() -> None:
    err = ValidationError(detail="slug too short")
    assert err.status == 400
    assert err.type == "/errors/validation"
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && uv run pytest tests/test_errors.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/errors.py
from __future__ import annotations

from typing import Any


class HangarError(Exception):
    """Base exception mapped to RFC 7807 Problem+JSON by FastAPI handler."""

    def __init__(
        self,
        *,
        title: str,
        status: int,
        type_: str,
        detail: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail or title)
        self.title = title
        self.status = status
        self.type = type_
        self.detail = detail
        self.extras = extras or {}

    def to_problem(self) -> dict[str, Any]:
        problem: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
        }
        if self.detail is not None:
            problem["detail"] = self.detail
        problem.update(self.extras)
        return problem


class NotFoundError(HangarError):
    def __init__(self, entity: str, identifier: str) -> None:
        super().__init__(
            title="Not Found",
            status=404,
            type_="/errors/not-found",
            detail=f"{entity} {identifier!r} does not exist",
        )


class ConflictError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(title="Conflict", status=409, type_="/errors/conflict", detail=detail)


class UnauthorizedError(HangarError):
    def __init__(self, *, detail: str | None = None) -> None:
        super().__init__(
            title="Unauthorized",
            status=401,
            type_="/errors/unauthorized",
            detail=detail or "authentication required",
        )


class ForbiddenError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(
            title="Forbidden", status=403, type_="/errors/forbidden", detail=detail
        )


class ValidationError(HangarError):
    def __init__(self, *, detail: str) -> None:
        super().__init__(
            title="Validation Failed",
            status=400,
            type_="/errors/validation",
            detail=detail,
        )


class RateLimitedError(HangarError):
    def __init__(self, *, detail: str, retry_after_s: int) -> None:
        super().__init__(
            title="Too Many Requests",
            status=429,
            type_="/errors/rate-limited",
            detail=detail,
            extras={"retry_after_s": retry_after_s},
        )
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_errors.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Mypy + ruff**

```bash
uv run ruff check . && uv run mypy app tests
```

Both clean.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/errors.py backend/tests/test_errors.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): HangarError hierarchy + Problem+JSON dict conversion

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.2 — Crypto module (AES-256-GCM envelope)

**Files:**
- Create: `backend/app/core/crypto.py`
- Create: `backend/tests/test_crypto.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_crypto.py
import base64
import secrets

import pytest

from app.core.crypto import (
    decrypt_with_dek,
    decrypt_with_master,
    encrypt_with_dek,
    encrypt_with_master,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)


@pytest.fixture
def master_key_b64() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")


def test_generate_dek_is_32_bytes() -> None:
    dek = generate_dek()
    assert isinstance(dek, bytes)
    assert len(dek) == 32


def test_wrap_unwrap_roundtrip(master_key_b64: str) -> None:
    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=master_key_b64)
    assert isinstance(wrapped, str)
    assert wrapped != dek.hex()

    unwrapped = unwrap_dek(wrapped, master_key_b64=master_key_b64)
    assert unwrapped == dek


def test_unwrap_fails_with_wrong_master_key(master_key_b64: str) -> None:
    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=master_key_b64)

    wrong_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    with pytest.raises(Exception):  # cryptography raises InvalidTag
        unwrap_dek(wrapped, master_key_b64=wrong_key)


def test_encrypt_decrypt_with_dek_roundtrip() -> None:
    dek = generate_dek()
    plaintext = "ghp_supersecrettokenvalue123456"

    ciphertext = encrypt_with_dek(plaintext, dek=dek)
    assert isinstance(ciphertext, str)
    assert ciphertext != plaintext

    decrypted = decrypt_with_dek(ciphertext, dek=dek)
    assert decrypted == plaintext


def test_encrypt_with_dek_produces_different_ciphertexts_each_time() -> None:
    dek = generate_dek()
    plaintext = "same input"

    c1 = encrypt_with_dek(plaintext, dek=dek)
    c2 = encrypt_with_dek(plaintext, dek=dek)
    assert c1 != c2  # random nonce makes each encryption unique


def test_encrypt_with_master_and_decrypt(master_key_b64: str) -> None:
    plaintext = "some data"
    ciphertext = encrypt_with_master(plaintext, master_key_b64=master_key_b64)
    decrypted = decrypt_with_master(ciphertext, master_key_b64=master_key_b64)
    assert decrypted == plaintext


def test_decrypt_with_dek_rejects_tampered_ciphertext() -> None:
    dek = generate_dek()
    ciphertext = encrypt_with_dek("x", dek=dek)

    # Flip one bit in the base64-decoded payload — decryption must raise
    raw = base64.urlsafe_b64decode(ciphertext + "==")
    tampered = raw[:15] + bytes([raw[15] ^ 0x01]) + raw[16:]
    tampered_b64 = base64.urlsafe_b64encode(tampered).decode().rstrip("=")

    with pytest.raises(Exception):
        decrypt_with_dek(tampered_b64, dek=dek)
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_crypto.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/crypto.py
"""AES-256-GCM envelope crypto for Hangar.

Layer 1: HANGAR_MASTER_KEY (32 bytes, env) wraps per-workspace DEKs.
Layer 2: DEK (32 bytes, per workspace) encrypts integration tokens and
         other workspace-scoped secrets at rest.

Every ciphertext payload is base64-urlsafe-encoded:

    ┌──────────┬──────────────┬────────────┐
    │ nonce 12 │ ciphertext n │ tag 16     │
    └──────────┴──────────────┴────────────┘

`cryptography.hazmat.primitives.ciphers.aead.AESGCM` embeds the auth tag
into the ciphertext, so our encoded layout is nonce + AESGCM.encrypt_output.
"""
from __future__ import annotations

import base64
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_BYTES = 12


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _master_key_bytes(master_key_b64: str) -> bytes:
    raw = _b64decode(master_key_b64)
    if len(raw) != 32:
        raise ValueError(f"HANGAR_MASTER_KEY must decode to 32 bytes (got {len(raw)})")
    return raw


def generate_dek() -> bytes:
    """Return a fresh 32-byte data encryption key."""
    return secrets.token_bytes(32)


def _encrypt(plaintext: bytes, key: bytes) -> str:
    aes = AESGCM(key)
    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = aes.encrypt(nonce, plaintext, associated_data=None)
    return _b64encode(nonce + ciphertext)


def _decrypt(payload_b64: str, key: bytes) -> bytes:
    raw = _b64decode(payload_b64)
    if len(raw) < _NONCE_BYTES + 16:
        raise ValueError("ciphertext too short")
    nonce, ciphertext = raw[:_NONCE_BYTES], raw[_NONCE_BYTES:]
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, associated_data=None)


def wrap_dek(dek: bytes, *, master_key_b64: str) -> str:
    """Encrypt a DEK with the server master key, return base64 string."""
    return _encrypt(dek, _master_key_bytes(master_key_b64))


def unwrap_dek(wrapped_b64: str, *, master_key_b64: str) -> bytes:
    """Decrypt a wrapped DEK, return 32 bytes."""
    return _decrypt(wrapped_b64, _master_key_bytes(master_key_b64))


def encrypt_with_dek(plaintext: str, *, dek: bytes) -> str:
    """Encrypt a UTF-8 string with a workspace DEK, return base64 payload."""
    return _encrypt(plaintext.encode("utf-8"), dek)


def decrypt_with_dek(payload_b64: str, *, dek: bytes) -> str:
    """Decrypt a workspace-DEK-encrypted payload, return UTF-8 string."""
    return _decrypt(payload_b64, dek).decode("utf-8")


def encrypt_with_master(plaintext: str, *, master_key_b64: str) -> str:
    """Convenience: encrypt directly with the master key (one-layer, small payloads)."""
    return _encrypt(plaintext.encode("utf-8"), _master_key_bytes(master_key_b64))


def decrypt_with_master(payload_b64: str, *, master_key_b64: str) -> str:
    """Convenience: decrypt master-encrypted payload."""
    return _decrypt(payload_b64, _master_key_bytes(master_key_b64)).decode("utf-8")
```

- [ ] **Step 4: Run — expect pass**

```bash
uv run pytest tests/test_crypto.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Ruff + mypy**

```bash
uv run ruff check . && uv run mypy app tests
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/crypto.py backend/tests/test_crypto.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): AES-256-GCM envelope crypto (master key wraps workspace DEKs)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.3 — Async Redis client

**Files:**
- Create: `backend/app/core/redis.py`
- Create: `backend/tests/test_redis.py`

Tests use a real Redis when `HANGAR_REDIS_URL` points at one. CI has Redis service. Locally, Docker-free environments skip via `pytest.mark.integration`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_redis.py
import pytest

from app.core.redis import get_redis

pytestmark = pytest.mark.integration


async def test_ping_and_set_get() -> None:
    r = await get_redis()
    assert await r.ping() is True

    await r.set("hangar-test-key", "value", ex=10)
    val = await r.get("hangar-test-key")
    assert val == "value"

    await r.delete("hangar-test-key")


async def test_get_redis_returns_singleton() -> None:
    r1 = await get_redis()
    r2 = await get_redis()
    assert r1 is r2
```

- [ ] **Step 2: Run — expect failure (collect-only is fine for local)**

```bash
uv run pytest tests/test_redis.py --collect-only -q
```

Expected: tests collect without error.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/redis.py
from __future__ import annotations

import asyncio

from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_redis: Redis | None = None
_lock = asyncio.Lock()


async def get_redis() -> Redis:
    """Return a singleton async Redis client built from settings.redis_url."""
    global _redis
    if _redis is None:
        async with _lock:
            if _redis is None:
                _redis = from_url(
                    get_settings().redis_url,
                    decode_responses=True,
                    encoding="utf-8",
                )
    return _redis


async def close_redis() -> None:
    """Close the shared client and clear the singleton (call on app shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
```

- [ ] **Step 4: Collect + (if Redis reachable) run**

```bash
uv run pytest tests/test_redis.py --collect-only -q
# If you have a local Redis running (or CI), actual run:
uv run pytest tests/test_redis.py -v
```

Expected in CI: `2 passed`. Locally without Redis: collect succeeds, execution may fail with connection refused — acceptable.

- [ ] **Step 5: Ruff + mypy**

```bash
uv run ruff check . && uv run mypy app tests
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/redis.py backend/tests/test_redis.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): async Redis client singleton keyed on HANGAR_REDIS_URL

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.4 — Token-bucket rate-limiter

**Files:**
- Create: `backend/app/core/rate_limit.py`
- Create: `backend/tests/test_rate_limit.py`

Token-bucket algorithm implemented via Redis Lua script — atomic, deterministic. Returns `(allowed: bool, retry_after_s: int)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_rate_limit.py
import asyncio
import uuid

import pytest

from app.core.rate_limit import check_and_consume

pytestmark = pytest.mark.integration


async def test_allows_up_to_capacity() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    capacity = 3
    refill_rate = 0.1  # 1 token per 10s

    for _ in range(capacity):
        allowed, _ = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
        assert allowed is True


async def test_denies_over_capacity() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    capacity = 2
    refill_rate = 0.01  # very slow refill

    for _ in range(capacity):
        allowed, _ = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
        assert allowed is True

    allowed, retry = await check_and_consume(key, capacity=capacity, refill_rate=refill_rate)
    assert allowed is False
    assert retry >= 1


async def test_refills_over_time() -> None:
    key = f"rl-test:{uuid.uuid4()}"
    # 1 token capacity, refill 5 tokens/sec → refill interval 200ms
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is True

    # Immediately denied
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is False

    # Wait for refill
    await asyncio.sleep(0.3)
    allowed, _ = await check_and_consume(key, capacity=1, refill_rate=5.0)
    assert allowed is True
```

- [ ] **Step 2: Run — expect failure**

```bash
uv run pytest tests/test_rate_limit.py --collect-only -q
```

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/rate_limit.py
"""Token-bucket rate limiter backed by Redis.

Each unique `key` gets an independent bucket. The Lua script below runs
atomically on the server: compute elapsed since last refill, add tokens
capped at capacity, deduct 1 if any remain, otherwise return (0, wait).
"""
from __future__ import annotations

import math

from app.core.redis import get_redis

# KEYS[1] = bucket key
# ARGV[1] = capacity (max tokens, float as string)
# ARGV[2] = refill_rate (tokens/sec, float as string)
# ARGV[3] = now_ms (integer milliseconds since epoch)
# ARGV[4] = ttl_ms (integer, expiry of the key)
#
# Returns [allowed (0|1), retry_after_ms (integer)]
_LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now_ms = tonumber(ARGV[3])
local ttl_ms = tonumber(ARGV[4])

local data = redis.call("HMGET", key, "tokens", "last_ms")
local tokens = tonumber(data[1])
local last_ms = tonumber(data[2])
if tokens == nil then
  tokens = capacity
  last_ms = now_ms
end

local elapsed = (now_ms - last_ms) / 1000.0
if elapsed < 0 then elapsed = 0 end
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
local retry_after_ms = 0
if tokens >= 1 then
  tokens = tokens - 1
  allowed = 1
else
  -- how long until we have 1 token?
  retry_after_ms = math.ceil((1 - tokens) / refill * 1000)
end

redis.call("HMSET", key, "tokens", tostring(tokens), "last_ms", tostring(now_ms))
redis.call("PEXPIRE", key, ttl_ms)
return {allowed, retry_after_ms}
"""


async def check_and_consume(
    key: str,
    *,
    capacity: int,
    refill_rate: float,
) -> tuple[bool, int]:
    """Atomically consume 1 token from `key`'s bucket.

    Args:
      key: Redis key identifying the bucket (caller should namespace).
      capacity: maximum tokens in bucket.
      refill_rate: tokens per second.

    Returns:
      (allowed, retry_after_seconds). retry_after is 0 when allowed, else >= 1.
    """
    import time

    redis = await get_redis()
    now_ms = int(time.time() * 1000)
    # Key expires 2x the time to fully refill, so stale buckets don't linger.
    ttl_ms = int(max(60_000, (capacity / max(refill_rate, 0.001)) * 2_000))

    result = await redis.eval(
        _LUA_TOKEN_BUCKET,
        1,
        key,
        str(capacity),
        str(refill_rate),
        str(now_ms),
        str(ttl_ms),
    )
    allowed_i, retry_ms = result  # type: ignore[misc]
    retry_s = math.ceil(int(retry_ms) / 1000) if int(retry_ms) > 0 else 0
    return bool(int(allowed_i)), retry_s
```

- [ ] **Step 4: Collect + optional run**

```bash
uv run pytest tests/test_rate_limit.py --collect-only -q
```

In CI: `uv run pytest tests/test_rate_limit.py -v` — expected `3 passed`.

- [ ] **Step 5: Ruff + mypy**

```bash
uv run ruff check . && uv run mypy app tests
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/rate_limit.py backend/tests/test_rate_limit.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): Redis-Lua token-bucket rate limiter

Atomic per-key token-bucket implemented as a single Lua script (capacity,
refill_rate, TTL). Returns (allowed, retry_after_seconds). Used by
Phase 3 auth routes (3/hour per email, 10/hour per IP) and Phase 4+
general routes (60/min per session).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.5 — Audit listener + contextvars

**Files:**
- Create: `backend/app/core/audit.py`
- Create: `backend/tests/test_audit.py`

The listener attaches to any `AsyncSession` and emits `AuditLog` rows for every `INSERT / UPDATE / DELETE` on tables other than `audit_log` itself. It reads actor + workspace from `contextvars.ContextVar` values set by middleware (Phase 3) or by tests directly.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_audit.py
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import (
    current_actor,
    current_workspace_id,
    install_audit_listener,
)
from app.core.ulid import new_ulid
from app.models import AuditLog, Project, User, Workspace

pytestmark = pytest.mark.integration


async def _bootstrap(session: AsyncSession) -> tuple[str, str, str]:
    user = User(email=f"audit-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()
    workspace = Workspace(slug=f"ws-{new_ulid()[:10]}", name="Audit WS", owner_id=user.id)
    session.add(workspace)
    await session.flush()
    return user.id, workspace.id, user.id


async def test_insert_emits_audit_row(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        project = Project(workspace_id=workspace_id, slug="audit-p", name="Audit P")
        session.add(project)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    rows = (await session.execute(
        select(AuditLog).where(AuditLog.entity == "projects")
    )).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.op == "create"
    assert row.entity_id == project.id
    assert row.actor == f"ui:{user_id}"
    assert row.workspace_id == workspace_id
    assert row.diff is not None
    assert row.diff.get("name") == [None, "Audit P"]


async def test_update_emits_audit_row_with_diff(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    project = Project(workspace_id=workspace_id, slug="u", name="Original")
    session.add(project)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        project.name = "Updated"
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    updates = (await session.execute(
        select(AuditLog).where(AuditLog.op == "update", AuditLog.entity == "projects")
    )).scalars().all()
    assert len(updates) == 1
    diff = updates[0].diff
    assert diff is not None
    assert diff.get("name") == ["Original", "Updated"]


async def test_delete_emits_audit_row(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    project = Project(workspace_id=workspace_id, slug="del", name="ToDelete")
    session.add(project)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user_id}")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        await session.delete(project)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    deletes = (await session.execute(
        select(AuditLog).where(AuditLog.op == "delete", AuditLog.entity == "projects")
    )).scalars().all()
    assert len(deletes) == 1


async def test_audit_log_itself_not_logged(session: AsyncSession) -> None:
    install_audit_listener()
    user_id, workspace_id, _ = await _bootstrap(session)

    token_actor = current_actor.set("worker:test")
    token_ws = current_workspace_id.set(workspace_id)
    try:
        manual = AuditLog(
            workspace_id=workspace_id, actor="worker:test", op="create",
            entity="stack_items", entity_id="01AAAA00000000000000000000",
            diff={"slug": [None, "foo"]},
        )
        session.add(manual)
        await session.flush()
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    all_audit = (await session.execute(select(AuditLog))).scalars().all()
    # Only our manually-inserted row should exist; the listener must not
    # have recursively created another entry for the AuditLog insert.
    assert len(all_audit) == 1
```

- [ ] **Step 2: Run — expect failure (ModuleNotFoundError)**

```bash
uv run pytest tests/test_audit.py --collect-only -q
```

- [ ] **Step 3: Write the implementation**

```python
# backend/app/core/audit.py
"""SQLAlchemy audit listener + request-scoped context vars.

`install_audit_listener()` wires a `before_flush` event on `AsyncSession`
that inspects `session.new`, `session.dirty`, and `session.deleted` and
emits `AuditLog` rows for each non-`AuditLog` instance.

Actor and workspace_id come from contextvars set by middleware (Phase 3)
or tests. If they aren't set when a write happens, the listener falls
back to `actor='system'` and uses the record's `workspace_id` attribute
when the entity has one — otherwise the write is allowed but logged
with `workspace_id=NULL`-safe placeholder (the `audit_log.workspace_id`
column is NOT NULL, so entities without workspace_id will raise).
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.ulid import new_ulid
from app.models import AuditLog

current_actor: ContextVar[str] = ContextVar("current_actor", default="system")
current_workspace_id: ContextVar[str | None] = ContextVar("current_workspace_id", default=None)

_installed = False


def _extract_diff(obj: Any, op: str) -> dict[str, Any]:
    """Return {column: [before, after]} for update, {column: [None, after]} for create,
    {column: [before, None]} for delete. Skips columns whose value didn't change."""
    state = inspect(obj)
    mapper = state.mapper

    diff: dict[str, Any] = {}
    for col in mapper.column_attrs:
        name = col.key
        hist = state.attrs[name].history
        if op == "create":
            if hist.added:
                value = hist.added[0]
                diff[name] = [None, _jsonify(value)]
        elif op == "update":
            if hist.has_changes():
                before = hist.deleted[0] if hist.deleted else None
                after = hist.added[0] if hist.added else None
                diff[name] = [_jsonify(before), _jsonify(after)]
        elif op == "delete":
            # On delete, history has the original loaded value in `unchanged` or `deleted`.
            current_val = getattr(obj, name, None)
            diff[name] = [_jsonify(current_val), None]
    return diff


def _jsonify(value: Any) -> Any:
    """Convert non-JSON-safe values (datetime, bytes) to strings."""
    from datetime import date, datetime
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


def install_audit_listener() -> None:
    """Idempotently attach the audit listener to all AsyncSession instances."""
    global _installed
    if _installed:
        return

    @event.listens_for(Session, "before_flush")
    def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
        actor = current_actor.get()
        workspace_id = current_workspace_id.get()

        audit_rows: list[AuditLog] = []

        def _collect(obj: Any, op: str) -> None:
            if isinstance(obj, AuditLog):
                return
            diff = _extract_diff(obj, op)
            ws_id = workspace_id or getattr(obj, "workspace_id", None)
            if not isinstance(ws_id, str):
                return  # no workspace context → skip audit (e.g. users, magic_link_tokens)
            entity = obj.__tablename__
            entity_id = getattr(obj, "id", None)
            if not isinstance(entity_id, str):
                return  # composite PKs (workspace_members, project_stack, project_tags) — skip for v1
            audit_rows.append(AuditLog(
                id=new_ulid(),
                workspace_id=ws_id,
                actor=actor,
                op=op,
                entity=entity,
                entity_id=entity_id,
                diff=diff,
            ))

        for obj in list(session.new):
            _collect(obj, "create")
        for obj in list(session.dirty):
            if session.is_modified(obj, include_collections=False):
                _collect(obj, "update")
        for obj in list(session.deleted):
            _collect(obj, "delete")

        for row in audit_rows:
            session.add(row)

    _installed = True
```

- [ ] **Step 4: Collect + (CI) run**

```bash
uv run pytest tests/test_audit.py --collect-only -q
```

In CI: `uv run pytest tests/test_audit.py -v` — expected `4 passed`.

- [ ] **Step 5: Ruff + mypy**

```bash
uv run ruff check . && uv run mypy app tests
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/audit.py backend/tests/test_audit.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
feat(backend): audit listener on SQLAlchemy before_flush + contextvars

- current_actor + current_workspace_id: request-scoped ContextVars
- install_audit_listener(): idempotent hook emitting AuditLog rows
  for every INSERT/UPDATE/DELETE on workspace-scoped tables
- skips AuditLog itself (no recursion), skips composite-PK rows
  (workspace_members, project_stack, project_tags — tracked via
  parent-entity updates instead), skips rows without workspace context
- diff JSONB shape: {col: [before, after]}, before=null on create,
  after=null on delete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2.6 — Integration sanity check (whole Phase 2 runs together)

**Files:**
- Create: `backend/tests/test_phase2_integration.py`

One test that exercises crypto + Redis + rate-limit + audit in combination, to catch any cross-module regressions.

- [ ] **Step 1: Write the test**

```python
# backend/tests/test_phase2_integration.py
from __future__ import annotations

import base64
import secrets
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import current_actor, current_workspace_id, install_audit_listener
from app.core.crypto import decrypt_with_dek, encrypt_with_dek, generate_dek, unwrap_dek, wrap_dek
from app.core.rate_limit import check_and_consume
from app.core.ulid import new_ulid
from app.models import AuditLog, Integration, User, Workspace, WorkspaceKey

pytestmark = pytest.mark.integration


async def test_workspace_creation_full_stack(session: AsyncSession) -> None:
    """User signs up → workspace created → DEK generated + wrapped → GitHub token encrypted.
    Rate-limit allows N ops; audit log captures every write."""
    install_audit_listener()

    master_key_b64 = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")

    # Bootstrap user + workspace
    user = User(email=f"int-{new_ulid()}@example.com")
    session.add(user)
    await session.flush()

    workspace = Workspace(slug=f"ws-{new_ulid()[:10]}", name="Integration", owner_id=user.id)
    session.add(workspace)
    await session.flush()

    token_actor = current_actor.set(f"ui:{user.id}")
    token_ws = current_workspace_id.set(workspace.id)
    try:
        # Generate + wrap DEK
        dek = generate_dek()
        wrapped = wrap_dek(dek, master_key_b64=master_key_b64)
        session.add(WorkspaceKey(workspace_id=workspace.id, dek_ciphertext=wrapped))

        # Encrypt a fake GitHub token with the DEK
        gh_token = "ghp_" + secrets.token_hex(20)
        ciphertext = encrypt_with_dek(gh_token, dek=dek)
        session.add(Integration(
            workspace_id=workspace.id, kind="github",
            config={"login": "lenny"}, token_ciphertext=ciphertext,
        ))
        await session.flush()

        # Round-trip: read the integration back, unwrap DEK, decrypt token
        result = await session.execute(
            select(Integration).where(
                Integration.workspace_id == workspace.id, Integration.kind == "github"
            )
        )
        stored = result.scalar_one()
        assert stored.token_ciphertext

        wk = (await session.execute(
            select(WorkspaceKey).where(WorkspaceKey.workspace_id == workspace.id)
        )).scalar_one()
        dek_out = unwrap_dek(wk.dek_ciphertext, master_key_b64=master_key_b64)
        recovered = decrypt_with_dek(stored.token_ciphertext, dek=dek_out)
        assert recovered == gh_token

        # Rate-limit: 2 attempts should pass, 3rd should fail
        rl_key = f"phase2-rl-{uuid.uuid4()}"
        r1, _ = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        r2, _ = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        r3, retry = await check_and_consume(rl_key, capacity=2, refill_rate=0.01)
        assert r1 is True
        assert r2 is True
        assert r3 is False
        assert retry >= 1
    finally:
        current_actor.reset(token_actor)
        current_workspace_id.reset(token_ws)

    # Audit captured the workspace-scoped writes (not user, not workspace itself —
    # those were created without an active workspace context).
    audit_rows = (await session.execute(select(AuditLog))).scalars().all()
    entities = {row.entity for row in audit_rows}
    assert "integrations" in entities
    assert "workspace_keys" in entities
```

- [ ] **Step 2: Collect**

```bash
uv run pytest tests/test_phase2_integration.py --collect-only -q
```

In CI: `uv run pytest tests/test_phase2_integration.py -v` — expected `1 passed`.

- [ ] **Step 3: Full suite sanity**

```bash
uv run ruff check .
uv run mypy app tests
uv run pytest tests/test_healthz.py tests/test_config.py tests/test_ulid.py tests/test_errors.py tests/test_crypto.py -v
uv run pytest --collect-only -q
```

All green. Collect count should be 14 (Phase 1) + 1 (errors: 7 tests) + 1 (crypto: 7 tests) + 1 (redis: 2 tests) + 1 (rate_limit: 3 tests) + 1 (audit: 4 tests) + 1 (phase2 integration: 1 test) = totally **38 tests collected**.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_phase2_integration.py
git -c user.email="lennystepn@gmail.com" -c user.name="Lenny" commit -m "$(cat <<'EOF'
test(backend): Phase 2 cross-module integration (crypto + redis + rate-limit + audit)

Covers: user signup → workspace creation → DEK generation + wrap →
GitHub token encryption via DEK → full decrypt round-trip via master key
unwrap → rate-limit deny after capacity → audit log captures integrations
and workspace_keys writes under (actor, workspace_id) context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase 2 complete when

- [ ] `app/core/{errors,crypto,redis,rate_limit,audit}.py` all exist with modules as specified.
- [ ] DB-free tests pass locally: `test_healthz`, `test_config`, `test_ulid`, `test_errors`, `test_crypto` (24+ tests).
- [ ] DB+Redis-dependent tests collect without error locally (9 additional tests: test_redis 2 + test_rate_limit 3 + test_audit 4 + test_phase2_integration 1).
- [ ] Ruff + mypy strict both green.
- [ ] 6 Phase 2 commits on `main` (Task 2.1 through 2.6) with exact subject lines.
- [ ] CI on `main` exercises all tests (including DB + Redis ones) and is green.

Phase 3 (auth: magic-link request/verify/logout + session middleware + Resend) depends on all of these.
