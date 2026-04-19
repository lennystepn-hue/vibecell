# Phase 5 — Projects CRUD + /switch

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** `/projects` collection + `/projects/:slug` item + `/projects/:slug/switch`. Returns projects without children (children land in Phase 6).

**Prerequisite:** Phase 4 complete (HEAD ≥ `9760bec`).

---

## Endpoints

```
GET    /api/v1/projects?status=&tag=&q=&cursor=&limit=  → paginated list
POST   /api/v1/projects                                 → create
GET    /api/v1/projects/:slug                           → project (basic fields)
PATCH  /api/v1/projects/:slug                           → partial update
DELETE /api/v1/projects/:slug                           → 204 hard-delete cascade
POST   /api/v1/projects/:slug/switch                    → set active_project
```

All require session + workspace membership. `:slug` validates via existing regex. Active-workspace scope always applied.

---

## Files

```
backend/app/
├── api/v1/
│   └── projects.py                   full CRUD router
├── core/deps.py                       (modify) add require_project(slug)
├── schemas/
│   └── project.py                    ProjectOut, ProjectCreate, ProjectUpdate, ProjectListItem, ProjectListPage
├── services/
│   └── project.py                    list_projects, create_project, update_project, delete_project, set_active
├── models/project.py                  (no changes — existing ORM is sufficient)
└── main.py                            (modify) mount projects router
tests/
├── test_projects_list.py
├── test_projects_create.py
├── test_projects_get.py
├── test_projects_patch.py
├── test_projects_delete.py
└── test_projects_switch.py
```

---

## Task 5.1 — Schemas

**File:** `backend/app/schemas/project.py`

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$"
_VALID_STATUSES = {"idea", "building", "live", "paused", "shipped", "archived", "dead"}


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    emoji: str | None = None
    color: str | None = None
    pitch: str | None = None
    status: str


class ProjectOut(ProjectListItem):
    # Full project detail, without children (children arrive in Phase 6).
    is_public: int
    archived_at: str | None = None


class ProjectListPage(BaseModel):
    items: list[ProjectListItem]
    next_cursor: str | None = None


class ProjectCreate(BaseModel):
    slug: str = Field(..., pattern=_SLUG_RE, min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=20)
    pitch: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="building")

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=20)
    pitch: str | None = Field(default=None, max_length=2000)
    status: str | None = None
    is_public: int | None = None

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v
```

Commit: `feat(backend): project pydantic schemas (create/update/list/out)`

---

## Task 5.2 — Project service

**File:** `backend/app/services/project.py`

```python
"""Project CRUD + active-project tracking."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import ActiveProject, Project, ProjectTag, Tag

_RESERVED_SLUGS: frozenset[str] = frozenset(
    {"api", "admin", "public", "app", "www", "import", "settings", "billing", "auth"}
)


async def list_projects(
    db: AsyncSession,
    *,
    workspace_id: str,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[Project], str | None]:
    """Return (items, next_cursor). Cursor is the last item's created_at ISO string."""
    stmt = select(Project).where(Project.workspace_id == workspace_id)
    if status is not None:
        stmt = stmt.where(Project.status == status)
    if tag is not None:
        stmt = stmt.join(ProjectTag, ProjectTag.project_id == Project.id).join(
            Tag, and_(Tag.id == ProjectTag.tag_id, Tag.workspace_id == workspace_id)
        ).where(Tag.name == tag)
    if q is not None:
        pattern = f"%{q}%"
        stmt = stmt.where(Project.name.ilike(pattern) | Project.pitch.ilike(pattern))
    if cursor is not None:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as e:
            raise ValidationError(detail=f"invalid cursor: {e}") from e
        stmt = stmt.where(Project.created_at < cursor_dt)

    stmt = stmt.order_by(Project.created_at.desc()).limit(limit + 1)
    rows = (await db.execute(stmt)).scalars().all()

    has_more = len(rows) > limit
    items = list(rows[:limit])
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return items, next_cursor


async def get_project(db: AsyncSession, *, workspace_id: str, slug: str) -> Project:
    result = await db.execute(
        select(Project).where(Project.workspace_id == workspace_id, Project.slug == slug)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", slug)
    return project


async def create_project(
    db: AsyncSession,
    *,
    workspace_id: str,
    slug: str,
    name: str,
    emoji: str | None = None,
    color: str | None = None,
    pitch: str | None = None,
    status: str = "building",
) -> Project:
    if slug in _RESERVED_SLUGS:
        raise ValidationError(detail=f"slug {slug!r} is reserved")

    existing = (await db.execute(
        select(Project.id).where(
            Project.workspace_id == workspace_id, Project.slug == slug
        )
    )).first()
    if existing is not None:
        raise ConflictError(detail=f"project slug {slug!r} already exists in this workspace")

    project = Project(
        id=new_ulid(),
        workspace_id=workspace_id,
        slug=slug,
        name=name,
        emoji=emoji,
        color=color,
        pitch=pitch,
        status=status,
    )
    db.add(project)
    await db.flush()
    return project


async def update_project(
    db: AsyncSession,
    *,
    project: Project,
    name: str | None = None,
    emoji: str | None = None,
    color: str | None = None,
    pitch: str | None = None,
    status: str | None = None,
    is_public: int | None = None,
) -> Project:
    if name is not None:
        project.name = name
    if emoji is not None:
        project.emoji = emoji
    if color is not None:
        project.color = color
    if pitch is not None:
        project.pitch = pitch
    if status is not None:
        project.status = status
        if status == "archived":
            project.archived_at = datetime.now(UTC)
    if is_public is not None:
        project.is_public = is_public
    await db.flush()
    return project


async def delete_project(db: AsyncSession, *, project: Project) -> None:
    """Hard delete. Cascade removes all child rows (repos, links, etc.)."""
    await db.delete(project)
    await db.flush()


async def set_active_project(
    db: AsyncSession, *, workspace_id: str, user_id: str, project: Project,
) -> ActiveProject:
    existing = (await db.execute(
        select(ActiveProject).where(ActiveProject.workspace_id == workspace_id)
    )).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is None:
        row = ActiveProject(
            workspace_id=workspace_id,
            user_id=user_id,
            project_id=project.id,
            set_at=now,
        )
        db.add(row)
    else:
        existing.user_id = user_id
        existing.project_id = project.id
        existing.set_at = now
        row = existing
    await db.flush()
    return row
```

Commit: `feat(backend): project service — list/get/create/update/delete/set_active`

---

## Task 5.3 — `require_project` dependency

**File:** modify `backend/app/core/deps.py`

Add at the bottom:

```python
@dataclass(frozen=True, slots=True)
class ProjectContext:
    project: Project
    workspace: Workspace
    user: User


async def require_project(
    slug: Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")],
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectContext:
    ws = (await db.execute(
        select(Workspace).where(Workspace.id == auth.active_workspace_id)
    )).scalar_one_or_none()
    if ws is None:
        raise NotFoundError("workspace", auth.active_workspace_id)
    # Membership already ensured by require_auth loading a valid workspace from the session.
    project = (await db.execute(
        select(Project).where(
            Project.workspace_id == ws.id, Project.slug == slug
        )
    )).scalar_one_or_none()
    if project is None:
        raise NotFoundError("project", slug)
    return ProjectContext(project=project, workspace=ws, user=auth.user)
```

Update imports at top of `deps.py`:
```python
from app.models import Project, User, Workspace, WorkspaceMember
```

Commit: `feat(backend): require_project dep — active-workspace-scoped project resolver`

---

## Task 5.4 — Projects router

**File:** `backend/app/api/v1/projects.py`

```python
"""Projects CRUD + active-project switch."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.schemas.project import (
    ProjectCreate,
    ProjectListItem,
    ProjectListPage,
    ProjectOut,
    ProjectUpdate,
)
from app.services.project import (
    create_project,
    delete_project,
    list_projects,
    set_active_project,
    update_project,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_out(project) -> ProjectOut:  # type: ignore[no-untyped-def]
    return ProjectOut(
        id=project.id,
        slug=project.slug,
        name=project.name,
        emoji=project.emoji,
        color=project.color,
        pitch=project.pitch,
        status=project.status,
        is_public=project.is_public,
        archived_at=project.archived_at.isoformat() if project.archived_at else None,
    )


@router.get("", response_model=ProjectListPage)
async def list_(
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    tag: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ProjectListPage:
    items, next_cursor = await list_projects(
        db,
        workspace_id=auth.active_workspace_id,
        status=status_filter,
        tag=tag,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return ProjectListPage(
        items=[ProjectListItem.model_validate(p) for p in items],
        next_cursor=next_cursor,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create(
    body: ProjectCreate,
    auth: Annotated[AuthContext, Depends(require_auth)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    project = await create_project(
        db,
        workspace_id=auth.active_workspace_id,
        slug=body.slug,
        name=body.name,
        emoji=body.emoji,
        color=body.color,
        pitch=body.pitch,
        status=body.status,
    )
    await db.commit()
    return _to_out(project)


@router.get("/{slug}", response_model=ProjectOut)
async def get(
    ctx: Annotated[ProjectContext, Depends(require_project)],
) -> ProjectOut:
    return _to_out(ctx.project)


@router.patch("/{slug}", response_model=ProjectOut)
async def patch(
    body: ProjectUpdate,
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    await update_project(
        db,
        project=ctx.project,
        name=body.name,
        emoji=body.emoji,
        color=body.color,
        pitch=body.pitch,
        status=body.status,
        is_public=body.is_public,
    )
    await db.commit()
    return _to_out(ctx.project)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await delete_project(db, project=ctx.project)
    await db.commit()


@router.post("/{slug}/switch", response_model=ProjectOut)
async def switch(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    await set_active_project(
        db,
        workspace_id=ctx.workspace.id,
        user_id=ctx.user.id,
        project=ctx.project,
    )
    await db.commit()
    return _to_out(ctx.project)
```

Wire in `main.py`:
```python
from app.api.v1.projects import router as projects_router
# ...
app.include_router(projects_router)
```

Commit: `feat(backend): projects CRUD router (list/create/get/patch/delete/switch)`

---

## Task 5.5 — Route tests (6 files)

All use the `_auth_helpers` module from Phase 4. Shared setup pattern.

**File:** `backend/tests/test_projects_list.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_list_empty_returns_empty_items(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-empty@example.com")
            resp = await c.get("/api/v1/projects")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"items": [], "next_cursor": None}


async def test_list_returns_created_projects(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-items@example.com")
            await c.post("/api/v1/projects", json={"slug": "butlr", "name": "Butlr"})
            await c.post("/api/v1/projects", json={"slug": "zapline", "name": "Zapline"})
            resp = await c.get("/api/v1/projects")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 2
    slugs = {p["slug"] for p in body["items"]}
    assert slugs == {"butlr", "zapline"}


async def test_list_filter_by_status(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-filter@example.com")
            await c.post("/api/v1/projects", json={"slug": "b", "name": "B", "status": "building"})
            await c.post("/api/v1/projects", json={"slug": "l", "name": "L", "status": "live"})
            resp = await c.get("/api/v1/projects?status=live")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "l"


async def test_list_filter_by_q(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "list-q@example.com")
            await c.post("/api/v1/projects", json={"slug": "alpha", "name": "Alpha Service"})
            await c.post("/api/v1/projects", json={"slug": "beta", "name": "Beta Service"})
            resp = await c.get("/api/v1/projects?q=alpha")
    finally:
        clear_db_override()
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["slug"] == "alpha"


async def test_list_401_without_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        resp = await c.get("/api/v1/projects")
    assert resp.status_code == 401
```

**File:** `backend/tests/test_projects_create.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_create_happy_path(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "create-p@example.com")
            resp = await c.post(
                "/api/v1/projects",
                json={"slug": "butlr", "name": "Butlr", "emoji": "🛎️", "pitch": "OpenClaw-as-a-Service"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "butlr"
    assert body["emoji"] == "🛎️"
    assert body["status"] == "building"  # default


async def test_create_rejects_reserved_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "reserved-p@example.com")
            resp = await c.post("/api/v1/projects", json={"slug": "api", "name": "X"})
    finally:
        clear_db_override()
    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/validation"


async def test_create_rejects_duplicate_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "dup-p@example.com")
            r1 = await c.post("/api/v1/projects", json={"slug": "dup", "name": "A"})
            r2 = await c.post("/api/v1/projects", json={"slug": "dup", "name": "B"})
    finally:
        clear_db_override()
    assert r1.status_code == 201
    assert r2.status_code == 409


async def test_create_rejects_invalid_status(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "bad-status@example.com")
            resp = await c.post(
                "/api/v1/projects",
                json={"slug": "x", "name": "X", "status": "nonsense"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 422
```

**File:** `backend/tests/test_projects_get.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_get_by_slug(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "my-p", "name": "MyP"})
            resp = await c.get("/api/v1/projects/my-p")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-p"


async def test_get_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "get-missing@example.com")
            resp = await c.get("/api/v1/projects/nonexistent")
    finally:
        clear_db_override()
    assert resp.status_code == 404
```

**File:** `backend/tests/test_projects_patch.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_patch_updates_fields(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "patch-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "proj", "name": "Original"})
            resp = await c.patch(
                "/api/v1/projects/proj",
                json={"name": "Renamed", "status": "live"},
            )
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "live"


async def test_patch_archived_sets_archived_at(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "archive-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "old", "name": "Old"})
            resp = await c.patch("/api/v1/projects/old", json={"status": "archived"})
    finally:
        clear_db_override()
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "archived"
    assert body["archived_at"] is not None
```

**File:** `backend/tests/test_projects_delete.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_delete_removes_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "del-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "gone", "name": "Gone"})
            r_del = await c.delete("/api/v1/projects/gone")
            r_get = await c.get("/api/v1/projects/gone")
    finally:
        clear_db_override()
    assert r_del.status_code == 204
    assert r_get.status_code == 404


async def test_delete_404_when_missing(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "del-missing@example.com")
            resp = await c.delete("/api/v1/projects/nope")
    finally:
        clear_db_override()
    assert resp.status_code == 404
```

**File:** `backend/tests/test_projects_switch.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import ActiveProject, Workspace
from tests._auth_helpers import clear_db_override, override_db, sign_in

pytestmark = pytest.mark.integration


async def test_switch_sets_active_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "switch-p@example.com")
            await c.post("/api/v1/projects", json={"slug": "alpha", "name": "A"})
            await c.post("/api/v1/projects", json={"slug": "beta", "name": "B"})
            r1 = await c.post("/api/v1/projects/beta/switch")
    finally:
        clear_db_override()
    assert r1.status_code == 200
    assert r1.json()["slug"] == "beta"

    # Verify ActiveProject row was written
    wsq = await session.execute(select(Workspace).where(Workspace.slug.icontains("switch-p")))
    ws = wsq.scalar_one()
    ap = (await session.execute(
        select(ActiveProject).where(ActiveProject.workspace_id == ws.id)
    )).scalar_one()
    assert ap.project_id  # set


async def test_switch_404_for_unknown_project(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "switch-missing@example.com")
            resp = await c.post("/api/v1/projects/nope/switch")
    finally:
        clear_db_override()
    assert resp.status_code == 404
```

Commit: `test(backend): project route tests (list/create/get/patch/delete/switch)`

---

## Phase 5 complete when

- [ ] 6 endpoints respond correctly.
- [ ] `ruff check .` + `mypy app tests` green.
- [ ] All tests pass (~80 total after Phase 5: 65 prior + ~15 new).
- [ ] 5 commits on main (5.1–5.5).
- [ ] Staging test run green.
