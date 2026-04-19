# Phase 4 — Workspaces & `/me`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** `GET /me` + full `/workspaces` CRUD. First auth-gated endpoints — this phase validates the session-middleware → contextvar → dependency-injection pipeline end-to-end.

**Prerequisite:** Phase 3 complete + staging verified (HEAD ≥ `25151da`, 53 tests pass).

---

## Endpoints

```
GET    /api/v1/me                       → { user, active_workspace, workspaces[] }
GET    /api/v1/workspaces               → [{ slug, name, role, plan }]
POST   /api/v1/workspaces               { slug, name } → workspace
GET    /api/v1/workspaces/:slug         → full workspace
PATCH  /api/v1/workspaces/:slug         { name? }
```

All require session cookie. Return 401 if missing/invalid. The `:slug` variants additionally 404 if not a member.

---

## Files

```
backend/app/
├── api/v1/
│   ├── me.py                  GET /me
│   └── workspaces.py          GET / POST / GET :slug / PATCH :slug
├── core/deps.py               require_auth + require_workspace_member deps
├── schemas/
│   ├── user.py                UserOut
│   └── workspace.py           WorkspaceOut, WorkspaceList, WorkspaceCreate, WorkspaceUpdate
├── services/
│   └── workspace.py           service layer (reserved-slug + collision handling)
└── main.py                    (modify) mount 2 new routers
tests/
├── test_me.py
├── test_workspace_list.py
├── test_workspace_create.py
├── test_workspace_get.py
└── test_workspace_patch.py
```

---

## Task 4.1 — `core/deps.py`: require_auth + require_workspace_member

**File:** `backend/app/core/deps.py`

```python
"""Reusable FastAPI dependencies for authenticated routes.

require_auth      — validates session cookie, loads user, 401 on missing/bad
require_workspace — resolves workspace by :slug path param, 404 if absent,
                    403 if user is not a member
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.models import User, Workspace, WorkspaceMember


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    active_workspace_id: str


async def require_auth(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    user_id = getattr(request.state, "user_id", None)
    workspace_id = getattr(request.state, "workspace_id", None)
    if not user_id or not workspace_id:
        raise UnauthorizedError()
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise UnauthorizedError(detail="user not found")
    return AuthContext(user=user, active_workspace_id=workspace_id)


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    workspace: Workspace
    user: User
    role: str


async def require_workspace_member(
    slug: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")],
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceContext:
    ws = (await db.execute(select(Workspace).where(Workspace.slug == slug))).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", slug)
    member = (await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == ws.id,
            WorkspaceMember.user_id == auth.user.id,
        )
    )).scalar_one_or_none()
    if member is None:
        raise ForbiddenError(detail="not a member of this workspace")
    return WorkspaceContext(workspace=ws, user=auth.user, role=member.role)
```

Verify import:
```bash
uv run python -c "from app.core.deps import require_auth, require_workspace_member, AuthContext, WorkspaceContext; print('ok')"
uv run ruff check . && uv run mypy app tests
```

Commit: `feat(backend): reusable require_auth + require_workspace_member deps`

---

## Task 4.2 — Schemas

**Files:** `backend/app/schemas/user.py`, `backend/app/schemas/workspace.py`

```python
# backend/app/schemas/user.py
from pydantic import BaseModel, ConfigDict, EmailStr


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    name: str | None = None
    handle: str | None = None
```

```python
# backend/app/schemas/workspace.py
from pydantic import BaseModel, ConfigDict, Field


_SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$"


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    plan: str


class WorkspaceListItem(BaseModel):
    slug: str
    name: str
    role: str
    plan: str


class WorkspaceCreate(BaseModel):
    slug: str = Field(..., pattern=_SLUG_RE, min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
```

Commit: `feat(backend): user + workspace pydantic schemas`

---

## Task 4.3 — Workspace service (slug reservation + collision)

**File:** `backend/app/services/workspace.py`

```python
"""Workspace lifecycle helpers beyond first-login bootstrap."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import generate_dek, wrap_dek
from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationError
from app.core.ulid import new_ulid
from app.models import User, Workspace, WorkspaceKey, WorkspaceMember

_RESERVED_SLUGS: frozenset[str] = frozenset(
    {"api", "admin", "public", "app", "www", "import", "settings", "billing", "auth"}
)


async def create_workspace(
    db: AsyncSession, *, owner: User, slug: str, name: str,
) -> Workspace:
    if slug in _RESERVED_SLUGS:
        raise ValidationError(detail=f"slug {slug!r} is reserved")

    existing = (await db.execute(select(Workspace.id).where(Workspace.slug == slug))).first()
    if existing is not None:
        raise ConflictError(detail=f"workspace slug {slug!r} already exists")

    ws = Workspace(id=new_ulid(), slug=slug, name=name, owner_id=owner.id)
    db.add(ws)
    await db.flush()

    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role="owner"))

    dek = generate_dek()
    wrapped = wrap_dek(dek, master_key_b64=get_settings().master_key)
    db.add(WorkspaceKey(workspace_id=ws.id, dek_ciphertext=wrapped))

    await db.flush()
    return ws
```

Commit: `feat(backend): create_workspace service (reserved slugs + DEK bootstrap)`

---

## Task 4.4 — GET /me router + test

**File:** `backend/app/api/v1/me.py`

```python
"""GET /me — return current user, active workspace, and all memberships."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Workspace, WorkspaceMember
from app.schemas.user import UserOut
from app.schemas.workspace import WorkspaceListItem, WorkspaceOut

router = APIRouter(prefix="/api/v1", tags=["me"])


class MeOut(BaseModel):
    user: UserOut
    active_workspace: WorkspaceOut
    workspaces: list[WorkspaceListItem]


@router.get("/me", response_model=MeOut)
async def me(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeOut:
    active_ws = (await db.execute(
        select(Workspace).where(Workspace.id == auth.active_workspace_id)
    )).scalar_one()

    rows = (await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == auth.user.id)
        .order_by(Workspace.created_at.asc())
    )).all()

    workspaces = [
        WorkspaceListItem(slug=ws.slug, name=ws.name, role=m.role, plan=ws.plan)
        for ws, m in rows
    ]
    return MeOut(
        user=UserOut.model_validate(auth.user),
        active_workspace=WorkspaceOut.model_validate(active_ws),
        workspaces=workspaces,
    )
```

**Test:** `backend/tests/test_me.py` — needs a helper that signs in and exercises `/me`. Pattern for all auth-gated tests: issue magic link → verify it (which sets the cookie) → use that cookie for subsequent requests.

```python
# backend/tests/test_me.py
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.services.login import issue_magic_link

pytestmark = pytest.mark.integration


def _override_db(session: AsyncSession) -> None:
    async def _fake_get_db() -> AsyncIterator[AsyncSession]:
        yield session
    app.dependency_overrides[get_db] = _fake_get_db


def _clear() -> None:
    app.dependency_overrides.pop(get_db, None)


async def _sign_in(c: AsyncClient, session: AsyncSession, email: str) -> None:
    """Issue a magic link + verify it so `c` ends up carrying the session cookie."""
    raw = await issue_magic_link(session, email=email)
    await session.flush()
    r = await c.get(f"/api/v1/auth/verify?token={raw}")
    assert r.status_code == 303


async def test_me_returns_user_and_active_workspace(session: AsyncSession) -> None:
    _override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await _sign_in(c, session, "me-test@example.com")
            resp = await c.get("/api/v1/me")
    finally:
        _clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "me-test@example.com"
    assert body["active_workspace"]["slug"]
    assert body["active_workspace"]["plan"] == "free"
    assert len(body["workspaces"]) == 1
    assert body["workspaces"][0]["role"] == "owner"


async def test_me_returns_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["type"] == "/errors/unauthorized"
```

Wire router in `main.py`:
```python
from app.api.v1.me import router as me_router
# ...
app.include_router(me_router)
```

Commit: `feat(backend): GET /me — user + active workspace + memberships`

---

## Task 4.5 — Workspaces router

**File:** `backend/app/api/v1/workspaces.py`

```python
"""Workspace CRUD — list, create, get, update."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, WorkspaceContext, require_auth, require_workspace_member
from app.models import Workspace, WorkspaceMember
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceOut,
    WorkspaceUpdate,
)
from app.services.workspace import create_workspace

router = APIRouter(prefix="/api/v1/workspaces", tags=["workspaces"])


@router.get("", response_model=list[WorkspaceListItem])
async def list_workspaces(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WorkspaceListItem]:
    rows = (await db.execute(
        select(Workspace, WorkspaceMember)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == auth.user.id)
        .order_by(Workspace.created_at.asc())
    )).all()
    return [
        WorkspaceListItem(slug=ws.slug, name=ws.name, role=m.role, plan=ws.plan)
        for ws, m in rows
    ]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: WorkspaceCreate,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceOut:
    ws = await create_workspace(db, owner=auth.user, slug=body.slug, name=body.name)
    await db.commit()
    return WorkspaceOut.model_validate(ws)


@router.get("/{slug}", response_model=WorkspaceOut)
async def get(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
) -> WorkspaceOut:
    return WorkspaceOut.model_validate(ctx.workspace)


@router.patch("/{slug}", response_model=WorkspaceOut)
async def update(
    body: WorkspaceUpdate,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceOut:
    if body.name is not None:
        ctx.workspace.name = body.name
    await db.commit()
    await db.refresh(ctx.workspace)
    return WorkspaceOut.model_validate(ctx.workspace)
```

Wire in `main.py`:
```python
from app.api.v1.workspaces import router as workspaces_router
# ...
app.include_router(workspaces_router)
```

Commit: `feat(backend): workspace CRUD router (list/create/get/patch)`

---

## Task 4.6 — Workspace route tests

**Files:** `backend/tests/test_workspace_list.py`, `test_workspace_create.py`, `test_workspace_get.py`, `test_workspace_patch.py`

Each file follows the pattern from `test_me.py`: `_override_db` + `_sign_in` helpers, then exercise. To avoid duplicating helpers across 5+ files, add a shared fixture/helper module.

**File:** `backend/tests/_auth_helpers.py`

```python
"""Shared helpers for auth-gated integration tests."""
from collections.abc import AsyncIterator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.main import app
from app.services.login import issue_magic_link


def override_db(session: AsyncSession) -> None:
    async def _fake_get_db() -> AsyncIterator[AsyncSession]:
        yield session
    app.dependency_overrides[get_db] = _fake_get_db


def clear_db_override() -> None:
    app.dependency_overrides.pop(get_db, None)


async def sign_in(c: AsyncClient, session: AsyncSession, email: str) -> None:
    raw = await issue_magic_link(session, email=email)
    await session.flush()
    r = await c.get(f"/api/v1/auth/verify?token={raw}")
    assert r.status_code == 303, f"sign-in failed: {r.status_code} {r.text}"
```

Update `test_me.py` to use these helpers (replacing the inline duplicates).

**File:** `backend/tests/test_workspace_list.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_list_workspaces_returns_default_on_first_login(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-test@example.com")
            resp = await c.get("/api/v1/workspaces")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["role"] == "owner"
    assert body[0]["plan"] == "free"


async def test_list_workspaces_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/workspaces")
    assert resp.status_code == 401
```

**File:** `backend/tests/test_workspace_create.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_create_workspace_happy_path(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "create-ws@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "lab", "name": "Lab"})
    finally:
        clear_db_override()

    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "lab"
    assert body["name"] == "Lab"
    assert body["plan"] == "free"


async def test_create_workspace_rejects_reserved_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "reserved@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "admin", "name": "X"})
    finally:
        clear_db_override()

    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/validation"


async def test_create_workspace_rejects_duplicate_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "dup@example.com")
            r1 = await c.post("/api/v1/workspaces", json={"slug": "duplo", "name": "A"})
            assert r1.status_code == 201
            r2 = await c.post("/api/v1/workspaces", json={"slug": "duplo", "name": "B"})
    finally:
        clear_db_override()

    assert r2.status_code == 409
    assert r2.json()["type"] == "/errors/conflict"


async def test_create_workspace_rejects_malformed_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "bad-slug@example.com")
            resp = await c.post("/api/v1/workspaces", json={"slug": "BAD SLUG", "name": "X"})
    finally:
        clear_db_override()

    assert resp.status_code == 422
```

**File:** `backend/tests/test_workspace_get.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_workspace_by_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-ws@example.com")
            # First list to discover the default workspace slug
            r = await c.get("/api/v1/workspaces")
            slug = r.json()[0]["slug"]
            resp = await c.get(f"/api/v1/workspaces/{slug}")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    assert resp.json()["slug"] == slug


async def test_get_workspace_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "missing@example.com")
            resp = await c.get("/api/v1/workspaces/nonexistent")
    finally:
        clear_db_override()

    assert resp.status_code == 404


async def test_get_workspace_403_when_not_member(session: AsyncSession) -> None:
    # User A creates a workspace "private-a", user B tries to access it
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "owner-a@example.com")
            await c.post("/api/v1/workspaces", json={"slug": "private-a", "name": "A"})
            # switch to user B
            await c.post("/api/v1/auth/logout")
            await sign_in(c, session, "user-b@example.com")
            resp = await c.get("/api/v1/workspaces/private-a")
    finally:
        clear_db_override()

    assert resp.status_code == 403
```

**File:** `backend/tests/test_workspace_patch.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_patch_workspace_name(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "patch-ws@example.com")
            r = await c.get("/api/v1/workspaces")
            slug = r.json()[0]["slug"]
            resp = await c.patch(f"/api/v1/workspaces/{slug}", json={"name": "Renamed"})
    finally:
        clear_db_override()

    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
```

Commit: `test(backend): workspace route tests (list/create/get/patch) + shared _auth_helpers`

---

## Phase 4 complete when

- [ ] 5 endpoints respond correctly (happy + 401 + 404 + 403 + 422 + 409 paths tested).
- [ ] `ruff check .` + `mypy app tests` green.
- [ ] `uv run pytest -v` green (>60 tests total after adding ~14 from this phase).
- [ ] 6 commits on main (4.1 through 4.6).
- [ ] Staging VPS tests pass.
