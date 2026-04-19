# Phase 7 — Catalog (stack-items + tags)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Searchable stack-items catalog + workspace-scoped tags CRUD. Enables frontend autocomplete in Phase 11+ (Cockpit stack chips, tag picker).

**Prerequisite:** Phase 6 complete (HEAD ≥ `5ae95da`).

---

## Endpoints

```
GET  /api/v1/stack-items?q=&kind=&limit=   global catalog search (shared across workspaces)
POST /api/v1/stack-items                   create custom stack_item (workspace adds own entries)
GET  /api/v1/tags                          list tags in active workspace
POST /api/v1/tags                          create tag in active workspace
```

---

## Files

```
backend/app/
├── api/v1/
│   ├── stack_items.py
│   └── tags.py
├── schemas/
│   ├── stack_item.py
│   └── tag.py
└── services/
    └── catalog.py
tests/
├── test_stack_items.py
└── test_tags.py
```

---

## Task 7.1 — Schemas

**File:** `backend/app/schemas/stack_item.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class StackItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    kind: str | None = None
    icon_url: str | None = None


class StackItemCreate(BaseModel):
    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9\-]{0,98}[a-z0-9]$", min_length=2, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=30)
    icon_url: str | None = Field(default=None, max_length=500)
```

**File:** `backend/app/schemas/tag.py`

```python
from pydantic import BaseModel, ConfigDict, Field


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    color: str | None = None


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=20)
```

Commit: `feat(backend): stack_item + tag pydantic schemas`

---

## Task 7.2 — Catalog service

**File:** `backend/app/services/catalog.py`

```python
"""Shared stack-items catalog + workspace tags."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.core.ulid import new_ulid
from app.models import StackItem, Tag


async def search_stack_items(
    db: AsyncSession,
    *,
    q: str | None = None,
    kind: str | None = None,
    limit: int = 50,
) -> list[StackItem]:
    stmt = select(StackItem)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(StackItem.slug.ilike(pattern) | StackItem.name.ilike(pattern))
    if kind:
        stmt = stmt.where(StackItem.kind == kind)
    stmt = stmt.order_by(StackItem.slug.asc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def create_stack_item(
    db: AsyncSession,
    *,
    slug: str,
    name: str,
    kind: str | None = None,
    icon_url: str | None = None,
) -> StackItem:
    existing = (await db.execute(
        select(StackItem.id).where(StackItem.slug == slug)
    )).first()
    if existing is not None:
        raise ConflictError(detail=f"stack_item {slug!r} already exists")
    item = StackItem(id=new_ulid(), slug=slug, name=name, kind=kind, icon_url=icon_url)
    db.add(item)
    await db.flush()
    return item


async def list_tags(db: AsyncSession, *, workspace_id: str) -> list[Tag]:
    stmt = select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name.asc())
    return list((await db.execute(stmt)).scalars())


async def create_tag(
    db: AsyncSession,
    *,
    workspace_id: str,
    name: str,
    color: str | None = None,
) -> Tag:
    existing = (await db.execute(
        select(Tag.id).where(Tag.workspace_id == workspace_id, Tag.name == name)
    )).first()
    if existing is not None:
        raise ConflictError(detail=f"tag {name!r} already exists in this workspace")
    tag = Tag(id=new_ulid(), workspace_id=workspace_id, name=name, color=color)
    db.add(tag)
    await db.flush()
    return tag
```

Commit: `feat(backend): catalog service (stack_items search + create, tags list + create)`

---

## Task 7.3 — stack_items router

**File:** `backend/app/api/v1/stack_items.py`

```python
"""Global stack-items catalog."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.schemas.stack_item import StackItemCreate, StackItemOut
from app.services import catalog as svc

router = APIRouter(prefix="/api/v1/stack-items", tags=["catalog"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("", response_model=list[StackItemOut])
async def list_(
    _auth: AuthDep,
    db: DbDep,
    q: str | None = None,
    kind: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[StackItemOut]:
    items = await svc.search_stack_items(db, q=q, kind=kind, limit=limit)
    return [StackItemOut.model_validate(i) for i in items]


@router.post("", response_model=StackItemOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: StackItemCreate,
    _auth: AuthDep,
    db: DbDep,
) -> StackItemOut:
    item = await svc.create_stack_item(
        db, slug=body.slug, name=body.name, kind=body.kind, icon_url=body.icon_url,
    )
    await db.commit()
    return StackItemOut.model_validate(item)
```

Commit: `feat(backend): GET/POST /stack-items router (search + create)`

---

## Task 7.4 — tags router

**File:** `backend/app/api/v1/tags.py`

```python
"""Workspace tags."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.schemas.tag import TagCreate, TagOut
from app.services import catalog as svc

router = APIRouter(prefix="/api/v1/tags", tags=["catalog"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("", response_model=list[TagOut])
async def list_(auth: AuthDep, db: DbDep) -> list[TagOut]:
    tags = await svc.list_tags(db, workspace_id=auth.active_workspace_id)
    return [TagOut.model_validate(t) for t in tags]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: TagCreate,
    auth: AuthDep,
    db: DbDep,
) -> TagOut:
    tag = await svc.create_tag(
        db, workspace_id=auth.active_workspace_id, name=body.name, color=body.color,
    )
    await db.commit()
    return TagOut.model_validate(tag)
```

Wire both routers in `main.py`:
```python
from app.api.v1.stack_items import router as stack_items_router
from app.api.v1.tags import router as tags_router
# ...
app.include_router(stack_items_router)
app.include_router(tags_router)
```

Commit: `feat(backend): GET/POST /tags router (workspace-scoped list + create)`

---

## Task 7.5 — Route tests

**File:** `backend/tests/test_stack_items.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_stack_items_list_returns_seeded_entries(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-list@example.com")
            resp = await c.get("/api/v1/stack-items")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    slugs = {i["slug"] for i in body}
    assert "fastapi" in slugs
    assert "vue" in slugs


async def test_stack_items_filter_by_q(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-q@example.com")
            resp = await c.get("/api/v1/stack-items?q=clau")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    slugs = {i["slug"] for i in resp.json()}
    assert "claude" in slugs


async def test_stack_items_filter_by_kind(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-kind@example.com")
            resp = await c.get("/api/v1/stack-items?kind=model")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    kinds = {i["kind"] for i in resp.json()}
    assert kinds == {"model"}


async def test_stack_items_create_custom(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-create@example.com")
            resp = await c.post(
                "/api/v1/stack-items",
                json={"slug": "my-custom-tool", "name": "My Custom Tool", "kind": "service"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201
    assert resp.json()["slug"] == "my-custom-tool"


async def test_stack_items_create_rejects_duplicate(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "stack-dup@example.com")
            resp = await c.post(
                "/api/v1/stack-items",
                json={"slug": "fastapi", "name": "FastAPI"},  # already seeded
            )
    finally:
        clear_db_override()
    assert resp.status_code == 409
```

**File:** `backend/tests/test_tags.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_tags_list_empty(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-empty@example.com")
            resp = await c.get("/api/v1/tags")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json() == []


async def test_tags_create_and_list(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-create@example.com")
            r_c = await c.post("/api/v1/tags", json={"name": "backend", "color": "#8ab4ff"})
            r_l = await c.get("/api/v1/tags")
    finally:
        clear_db_override()
    assert r_c.status_code == 201
    assert r_c.json()["name"] == "backend"
    body = r_l.json()
    assert len(body) == 1
    assert body[0]["color"] == "#8ab4ff"


async def test_tags_create_rejects_duplicate_per_workspace(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "tags-dup@example.com")
            await c.post("/api/v1/tags", json={"name": "dup"})
            r2 = await c.post("/api/v1/tags", json={"name": "dup"})
    finally:
        clear_db_override()
    assert r2.status_code == 409
```

Commit: `test(backend): stack_items + tags route tests`

---

## Phase 7 complete when

- [ ] 4 catalog endpoints working.
- [ ] Ruff + mypy green.
- [ ] ~104 tests pass on staging (96 prior + 8 new).
- [ ] 5 commits on main (7.1–7.5).
