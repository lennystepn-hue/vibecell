# Phase 8 — GitHub Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** GitHub OAuth (web flow) + encrypted token storage (via workspace DEK) + repo-list proxy + bulk-import creating projects with auto-filled metadata + per-project repo resync.

**Prerequisite:** Phase 7 complete (HEAD ≥ `9ecbefa`).

---

## Endpoints

```
GET    /api/v1/integrations                                → list integrations (connected_at, masked config)
GET    /api/v1/integrations/github/oauth-start             → 302 to github.com authorize
GET    /api/v1/integrations/github/oauth-callback?code=    → exchange code + store, 302 to /import/github
DELETE /api/v1/integrations/github                          → revoke + delete row
GET    /api/v1/integrations/github/repos?page=&q=          → proxy GitHub API, normalized list
POST   /api/v1/integrations/github/import                  { repos: [{ owner, name, as_slug? }] } → [{ slug, status }]
POST   /api/v1/projects/:slug/repo/resync                  → re-fetch metadata for linked GitHub repo
```

OAuth state is stored in a short-lived Redis key `gh-oauth-state:<state>` → `<workspace_id>:<user_id>`, 10min TTL.

---

## Files

```
backend/app/
├── api/v1/
│   ├── integrations.py                         4 endpoints: list + oauth-start + oauth-callback + DELETE github
│   └── github_repos.py                         repos list + import (2 endpoints)
├── api/v1/projects.py                          (modify) add /resync endpoint
├── schemas/
│   └── integration.py                          IntegrationOut, GitHubRepoOut, ImportRequest, ImportResult
├── services/
│   ├── github.py                               GitHub API client (OAuth exchange, repo list, repo metadata)
│   └── integration.py                          store/retrieve encrypted tokens
└── core/deps.py                                (no change)
tests/
├── test_github_oauth.py
├── test_github_repos.py
├── test_github_import.py
└── test_github_resync.py
```

---

## Task 8.1 — Schemas

**File:** `backend/app/schemas/integration.py`

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    connected_at: datetime
    config: dict[str, Any]


class GitHubRepoOut(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    private: bool
    default_branch: str
    language: str | None = None
    license_spdx: str | None = None
    homepage: str | None = None
    clone_url: str
    pushed_at: datetime | None = None


class ImportItem(BaseModel):
    owner: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    as_slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")


class ImportRequest(BaseModel):
    repos: list[ImportItem] = Field(..., min_length=1, max_length=100)


class ImportResultItem(BaseModel):
    owner: str
    name: str
    slug: str | None
    status: str  # "imported" | "skipped-duplicate" | "failed"
    detail: str | None = None


class ImportResponse(BaseModel):
    results: list[ImportResultItem]
```

Commit: `feat(backend): integration + github pydantic schemas`

---

## Task 8.2 — Integration service (encrypt/decrypt access tokens)

**File:** `backend/app/services/integration.py`

```python
"""Store integration tokens encrypted with the workspace DEK."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import (
    decrypt_with_dek,
    encrypt_with_dek,
    unwrap_dek,
)
from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Integration, WorkspaceKey


async def _dek_for_workspace(db: AsyncSession, workspace_id: str) -> bytes:
    wk = (await db.execute(
        select(WorkspaceKey).where(WorkspaceKey.workspace_id == workspace_id)
    )).scalar_one_or_none()
    if wk is None:
        raise NotFoundError("workspace_key", workspace_id)
    return unwrap_dek(wk.dek_ciphertext, master_key_b64=get_settings().master_key)


async def upsert_integration(
    db: AsyncSession,
    *,
    workspace_id: str,
    kind: str,
    raw_token: str,
    config: dict,
) -> Integration:
    dek = await _dek_for_workspace(db, workspace_id)
    ciphertext = encrypt_with_dek(raw_token, dek=dek)

    existing = (await db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id, Integration.kind == kind
        )
    )).scalar_one_or_none()

    if existing is not None:
        existing.token_ciphertext = ciphertext
        existing.config = config
        await db.flush()
        return existing

    integration = Integration(
        id=new_ulid(),
        workspace_id=workspace_id,
        kind=kind,
        token_ciphertext=ciphertext,
        config=config,
    )
    db.add(integration)
    await db.flush()
    return integration


async def get_integration(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> Integration | None:
    return (await db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id, Integration.kind == kind
        )
    )).scalar_one_or_none()


async def get_decrypted_token(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> str:
    integ = await get_integration(db, workspace_id=workspace_id, kind=kind)
    if integ is None or not integ.token_ciphertext:
        raise NotFoundError("integration", kind)
    dek = await _dek_for_workspace(db, workspace_id)
    return decrypt_with_dek(integ.token_ciphertext, dek=dek)


async def delete_integration(
    db: AsyncSession, *, workspace_id: str, kind: str,
) -> None:
    integ = await get_integration(db, workspace_id=workspace_id, kind=kind)
    if integ is None:
        raise NotFoundError("integration", kind)
    await db.delete(integ)
    await db.flush()


async def list_integrations(
    db: AsyncSession, *, workspace_id: str,
) -> list[Integration]:
    rows = (await db.execute(
        select(Integration)
        .where(Integration.workspace_id == workspace_id)
        .order_by(Integration.connected_at.desc())
    )).scalars()
    return list(rows)


def mask_config(config: dict) -> dict:
    """Strip any secret-like keys from config before returning to client."""
    return {k: v for k, v in config.items() if k not in {"access_token", "refresh_token", "token"}}
```

Commit: `feat(backend): integration service — encrypted token storage per workspace DEK`

---

## Task 8.3 — GitHub service (OAuth + API proxy)

**File:** `backend/app/services/github.py`

```python
"""GitHub API client (OAuth exchange + repo operations)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import HangarError

_GITHUB_OAUTH_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GITHUB_API = "https://api.github.com"


def authorize_url(*, state: str, redirect_uri: str) -> str:
    s = get_settings()
    from urllib.parse import urlencode

    params = {
        "client_id": s.github_client_id,
        "redirect_uri": redirect_uri,
        "scope": "read:user repo",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urlencode(params)}"


async def exchange_code(*, code: str, redirect_uri: str) -> str:
    """Return access_token from GitHub. Raises HangarError on failure."""
    s = get_settings()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            _GITHUB_OAUTH_TOKEN_URL,
            data={
                "client_id": s.github_client_id,
                "client_secret": s.github_client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code >= 400:
        raise HangarError(
            title="GitHub OAuth failed",
            status=502,
            type_="/errors/github-oauth",
            detail=f"token exchange returned {resp.status_code}",
        )
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise HangarError(
            title="GitHub OAuth failed",
            status=502,
            type_="/errors/github-oauth",
            detail=payload.get("error_description") or "no access_token in response",
        )
    return str(token)


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def me(token: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_GITHUB_API}/user", headers=_auth_headers(token))
    resp.raise_for_status()
    return resp.json()


async def list_user_repos(
    token: str, *, page: int = 1, per_page: int = 30, q: str | None = None,
) -> list[dict[str, Any]]:
    """List repos the authenticated user can access. `q` filters client-side by name."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/user/repos",
            headers=_auth_headers(token),
            params={"page": page, "per_page": per_page, "sort": "updated"},
        )
    resp.raise_for_status()
    repos: list[dict[str, Any]] = resp.json()
    if q:
        ql = q.lower()
        repos = [r for r in repos if ql in (r.get("name") or "").lower()]
    return repos


async def get_repo(token: str, owner: str, name: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_GITHUB_API}/repos/{owner}/{name}",
            headers=_auth_headers(token),
        )
    resp.raise_for_status()
    return resp.json()


def normalize_repo(gh: dict[str, Any]) -> dict[str, Any]:
    """Trim GitHub response to the fields we expose."""
    owner = gh.get("owner", {}).get("login", "")
    name = gh.get("name", "")
    full_name = gh.get("full_name") or f"{owner}/{name}"
    pushed_at_str = gh.get("pushed_at")
    pushed_at = datetime.fromisoformat(pushed_at_str.replace("Z", "+00:00")) if pushed_at_str else None
    return {
        "owner": owner,
        "name": name,
        "full_name": full_name,
        "description": gh.get("description"),
        "private": bool(gh.get("private", False)),
        "default_branch": gh.get("default_branch") or "main",
        "language": gh.get("language"),
        "license_spdx": (gh.get("license") or {}).get("spdx_id") if gh.get("license") else None,
        "homepage": gh.get("homepage"),
        "clone_url": gh.get("clone_url") or gh.get("ssh_url") or "",
        "pushed_at": pushed_at,
    }
```

Commit: `feat(backend): github service — OAuth exchange + repo list/get + normalize`

---

## Task 8.4 — Integrations router

**File:** `backend/app/api/v1/integrations.py`

```python
"""Integrations listing + GitHub OAuth flow."""
from __future__ import annotations

import secrets
from typing import Annotated
from urllib.parse import urljoin

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import HangarError, NotFoundError
from app.core.redis import get_redis
from app.schemas.integration import IntegrationOut
from app.services import github as github_svc
from app.services import integration as integ_svc

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]

_OAUTH_STATE_TTL = 600  # 10 minutes


def _oauth_redirect_uri() -> str:
    base = get_settings().base_url
    return urljoin(base + "/", "api/v1/integrations/github/oauth-callback")


@router.get("", response_model=list[IntegrationOut])
async def list_(auth: AuthDep, db: DbDep) -> list[IntegrationOut]:
    rows = await integ_svc.list_integrations(db, workspace_id=auth.active_workspace_id)
    return [
        IntegrationOut(
            id=r.id,
            kind=r.kind,
            connected_at=r.connected_at,
            config=integ_svc.mask_config(r.config or {}),
        )
        for r in rows
    ]


@router.get("/github/oauth-start")
async def github_oauth_start(auth: AuthDep) -> RedirectResponse:
    state = secrets.token_urlsafe(24)
    redis = await get_redis()
    await redis.set(
        f"gh-oauth-state:{state}",
        f"{auth.active_workspace_id}:{auth.user.id}",
        ex=_OAUTH_STATE_TTL,
    )
    url = github_svc.authorize_url(state=state, redirect_uri=_oauth_redirect_uri())
    return RedirectResponse(url=url, status_code=302)


@router.get("/github/oauth-callback")
async def github_oauth_callback(
    code: Annotated[str, Query(min_length=1)],
    state: Annotated[str, Query(min_length=1)],
    request: Request,
    db: DbDep,
) -> RedirectResponse:
    redis = await get_redis()
    key = f"gh-oauth-state:{state}"
    stored = await redis.get(key)
    if not stored:
        raise HangarError(
            title="OAuth state invalid or expired",
            status=400, type_="/errors/oauth-state",
        )
    await redis.delete(key)

    workspace_id, user_id = stored.split(":", 1)

    # Optional cross-check: the current session must match the starting user.
    session_user_id = getattr(request.state, "user_id", None)
    if session_user_id and session_user_id != user_id:
        raise HangarError(
            title="OAuth state user mismatch",
            status=400, type_="/errors/oauth-state",
        )

    access_token = await github_svc.exchange_code(
        code=code, redirect_uri=_oauth_redirect_uri(),
    )
    me = await github_svc.me(access_token)
    login = me.get("login")

    await integ_svc.upsert_integration(
        db,
        workspace_id=workspace_id,
        kind="github",
        raw_token=access_token,
        config={"login": login, "avatar_url": me.get("avatar_url")},
    )
    await db.commit()

    return RedirectResponse(url="/import/github", status_code=303)


@router.delete("/github", status_code=204)
async def delete_github(auth: AuthDep, db: DbDep) -> None:
    try:
        await integ_svc.delete_integration(
            db, workspace_id=auth.active_workspace_id, kind="github",
        )
    except NotFoundError:
        return
    await db.commit()
```

Wire in main.py.

Commit: `feat(backend): integrations router — list + github OAuth start/callback + delete`

---

## Task 8.5 — GitHub repos router + bulk import

**File:** `backend/app/api/v1/github_repos.py`

```python
"""GitHub repos listing + bulk import into projects."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.core.errors import NotFoundError
from app.models import Project
from app.schemas.integration import (
    GitHubRepoOut,
    ImportRequest,
    ImportResponse,
    ImportResultItem,
)
from app.services import github as github_svc
from app.services import integration as integ_svc
from app.services.project import create_project

router = APIRouter(prefix="/api/v1/integrations/github", tags=["integrations"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


@router.get("/repos", response_model=list[GitHubRepoOut])
async def list_repos(
    auth: AuthDep,
    db: DbDep,
    page: Annotated[int, Query(ge=1, le=100)] = 1,
    q: str | None = None,
) -> list[GitHubRepoOut]:
    token = await integ_svc.get_decrypted_token(
        db, workspace_id=auth.active_workspace_id, kind="github",
    )
    raw = await github_svc.list_user_repos(token, page=page, q=q)
    return [GitHubRepoOut(**github_svc.normalize_repo(r)) for r in raw]


def _derive_slug(name: str, taken: set[str]) -> str:
    """Produce a valid project slug from a GitHub repo name, with suffix if taken."""
    import re

    clean = re.sub(r"[^a-z0-9-]", "-", name.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    if len(clean) < 2:
        clean = f"proj-{clean}" if clean else "proj"
    clean = clean[:50]

    if clean not in taken:
        return clean
    i = 2
    while True:
        candidate = f"{clean}-{i}"[:50]
        if candidate not in taken:
            return candidate
        i += 1


@router.post("/import", response_model=ImportResponse)
async def bulk_import(
    body: ImportRequest,
    auth: AuthDep,
    db: DbDep,
) -> ImportResponse:
    from sqlalchemy import select
    from app.models import ProjectLink, ProjectRepo

    token = await integ_svc.get_decrypted_token(
        db, workspace_id=auth.active_workspace_id, kind="github",
    )

    # Snapshot existing project slugs in this workspace to compute uniqueness
    existing_slugs = set(
        (await db.execute(
            select(Project.slug).where(Project.workspace_id == auth.active_workspace_id)
        )).scalars()
    )

    results: list[ImportResultItem] = []

    for item in body.repos:
        try:
            gh = await github_svc.get_repo(token, item.owner, item.name)
        except Exception as e:  # noqa: BLE001
            results.append(ImportResultItem(
                owner=item.owner, name=item.name, slug=None,
                status="failed", detail=f"fetch: {e!s}",
            ))
            continue
        norm = github_svc.normalize_repo(gh)

        desired = item.as_slug or _derive_slug(norm["name"], existing_slugs)
        if desired in existing_slugs:
            results.append(ImportResultItem(
                owner=item.owner, name=item.name, slug=desired,
                status="skipped-duplicate", detail="slug already exists in this workspace",
            ))
            continue

        try:
            project = await create_project(
                db,
                workspace_id=auth.active_workspace_id,
                slug=desired,
                name=norm["name"].replace("-", " ").replace("_", " ").title(),
                emoji="📦",
                pitch=norm.get("description"),
                status="building",
            )
            # Attach GitHub repo
            from app.core.ulid import new_ulid
            db.add(ProjectRepo(
                id=new_ulid(),
                project_id=project.id,
                role="monorepo",
                git_url=norm["clone_url"],
                default_branch=norm["default_branch"],
                primary_lang=norm.get("language"),
                license=norm.get("license_spdx"),
            ))
            if norm.get("homepage"):
                db.add(ProjectLink(
                    id=new_ulid(),
                    project_id=project.id,
                    kind="live",
                    label="Homepage",
                    url=norm["homepage"],
                ))
            await db.flush()
            existing_slugs.add(desired)
            results.append(ImportResultItem(
                owner=item.owner, name=item.name, slug=desired, status="imported",
            ))
        except Exception as e:  # noqa: BLE001
            results.append(ImportResultItem(
                owner=item.owner, name=item.name, slug=desired,
                status="failed", detail=f"create: {e!s}",
            ))

    await db.commit()
    return ImportResponse(results=results)
```

Wire in main.py.

Commit: `feat(backend): github repos router — GET /repos + POST /import (bulk project creation)`

---

## Task 8.6 — Repo resync on project

Add to `backend/app/api/v1/projects.py` (append at bottom, keep existing routes):

```python
@router.post("/{slug}/repo/resync", response_model=ProjectOut)
async def resync_repo(
    ctx: Annotated[ProjectContext, Depends(require_project)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProjectOut:
    from sqlalchemy import select
    from app.models import ProjectRepo
    from app.services import github as github_svc
    from app.services import integration as integ_svc

    # Find the first repo with a GitHub-style git_url
    repos = list((await db.execute(
        select(ProjectRepo)
        .where(ProjectRepo.project_id == ctx.project.id)
        .order_by(ProjectRepo.id.asc())
    )).scalars())

    gh_repo = next((r for r in repos if r.git_url and "github.com" in r.git_url), None)
    if gh_repo is None:
        return _to_out(ctx.project)

    # Parse owner/name out of git_url (supports https and ssh forms)
    import re
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$", gh_repo.git_url or "")
    if not m:
        return _to_out(ctx.project)
    owner, name = m.group(1), m.group(2)

    token = await integ_svc.get_decrypted_token(
        db, workspace_id=ctx.workspace.id, kind="github",
    )
    gh = await github_svc.get_repo(token, owner, name)
    norm = github_svc.normalize_repo(gh)

    gh_repo.default_branch = norm["default_branch"]
    gh_repo.primary_lang = norm.get("language")
    gh_repo.license = norm.get("license_spdx")
    if not ctx.project.pitch and norm.get("description"):
        ctx.project.pitch = norm["description"]

    await db.commit()
    return _to_out(ctx.project)
```

Commit: `feat(backend): POST /projects/:slug/repo/resync refreshes GitHub metadata`

---

## Task 8.7 — Tests

Because GitHub calls need to be mocked, add a shared test helper that stubs httpx.AsyncClient used by `app.services.github`.

**File:** `backend/tests/_github_helpers.py`

```python
"""Test helpers for mocking GitHub API calls."""
from typing import Any
from unittest.mock import AsyncMock

import pytest


def patch_github(monkeypatch: pytest.MonkeyPatch, responses: dict[str, Any]) -> None:
    """Stub the `app.services.github` module's network-touching functions.

    `responses` is a dict with keys: "exchange_code", "me", "list_user_repos",
    "get_repo". Each value is the return value (or an Exception to raise).
    """
    import app.services.github as gh

    async def _call(name: str, value: Any, *args: Any, **kwargs: Any) -> Any:
        if isinstance(value, Exception):
            raise value
        return value

    for name in ("exchange_code", "me", "list_user_repos", "get_repo"):
        if name in responses:
            value = responses[name]
            mock = AsyncMock(return_value=value if not isinstance(value, Exception) else None)
            if isinstance(value, Exception):
                mock.side_effect = value
            monkeypatch.setattr(gh, name, mock)
```

**File:** `backend/tests/test_github_oauth.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Integration
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def test_oauth_start_redirects_to_github(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-start@example.com")
            resp = await c.get("/api/v1/integrations/github/oauth-start")
    finally:
        clear_db_override()
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("https://github.com/login/oauth/authorize?")
    assert "state=" in location


async def test_oauth_callback_stores_encrypted_token(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake_token_123",
        "me": {"login": "lenny", "avatar_url": "https://avatar"},
    })
    # Pre-plant an OAuth state in Redis
    redis = await get_redis()
    state = "teststate123"
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-cb@example.com")
            # Pull the workspace_id + user_id from /me
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]
            from sqlalchemy import select
            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "oauth-cb@example.com")
            )).scalar_one()

            await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)

            resp = await c.get(
                f"/api/v1/integrations/github/oauth-callback?code=fake&state={state}"
            )
    finally:
        clear_db_override()

    assert resp.status_code == 303
    assert resp.headers["location"] == "/import/github"

    integ = (await session.execute(
        select(Integration).where(
            Integration.workspace_id == ws_id, Integration.kind == "github"
        )
    )).scalar_one()
    assert integ.token_ciphertext is not None
    assert integ.config.get("login") == "lenny"


async def test_oauth_callback_rejects_expired_state(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-expired@example.com")
            resp = await c.get(
                "/api/v1/integrations/github/oauth-callback?code=fake&state=nonexistent"
            )
    finally:
        clear_db_override()
    assert resp.status_code == 400
    assert resp.json()["type"] == "/errors/oauth-state"


async def test_delete_github_integration(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake",
        "me": {"login": "x"},
    })
    redis = await get_redis()
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "oauth-del@example.com")
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]
            from sqlalchemy import select
            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "oauth-del@example.com")
            )).scalar_one()

            state = "deltest"
            await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
            await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")

            resp = await c.delete("/api/v1/integrations/github")
    finally:
        clear_db_override()
    assert resp.status_code == 204


async def test_integrations_list(session: AsyncSession) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await sign_in(c, session, "integrations-list@example.com")
            resp = await c.get("/api/v1/integrations")
    finally:
        clear_db_override()
    assert resp.status_code == 200
    assert resp.json() == []
```

**File:** `backend/tests/test_github_repos.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def _setup_github_connected(
    c: AsyncClient, session: AsyncSession, email: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sign in + attach a fake github integration via OAuth callback."""
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake_token",
        "me": {"login": "lenny"},
    })
    await sign_in(c, session, email)
    me = (await c.get("/api/v1/me")).json()
    ws_slug = me["active_workspace"]["slug"]

    from sqlalchemy import select
    from app.models import User, Workspace
    ws_id = (await session.execute(
        select(Workspace.id).where(Workspace.slug == ws_slug)
    )).scalar_one()
    user_id = (await session.execute(
        select(User.id).where(User.email == email)
    )).scalar_one()

    redis = await get_redis()
    state = f"state-{email}"
    await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
    r = await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")
    assert r.status_code == 303


async def test_list_repos_returns_normalized_response(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await _setup_github_connected(c, session, "repos-list@example.com", monkeypatch)

            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake_token",
                "me": {"login": "lenny"},
                "list_user_repos": [
                    {
                        "name": "butlr",
                        "owner": {"login": "lenny"},
                        "full_name": "lenny/butlr",
                        "description": "Openclaw",
                        "private": True,
                        "default_branch": "main",
                        "language": "Python",
                        "license": {"spdx_id": "MIT"},
                        "homepage": "https://butlr.cloud",
                        "clone_url": "https://github.com/lenny/butlr.git",
                        "pushed_at": "2026-04-18T10:00:00Z",
                    },
                ],
            })
            resp = await c.get("/api/v1/integrations/github/repos")
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["owner"] == "lenny"
    assert body[0]["name"] == "butlr"
    assert body[0]["language"] == "Python"
    assert body[0]["license_spdx"] == "MIT"
```

**File:** `backend/tests/test_github_import.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import Project, ProjectRepo
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def _setup_connected(
    c: AsyncClient, session: AsyncSession, email: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_github(monkeypatch, {
        "exchange_code": "ghp_fake",
        "me": {"login": "lenny"},
    })
    await sign_in(c, session, email)
    me = (await c.get("/api/v1/me")).json()
    ws_slug = me["active_workspace"]["slug"]

    from app.models import User, Workspace
    ws_id = (await session.execute(
        select(Workspace.id).where(Workspace.slug == ws_slug)
    )).scalar_one()
    user_id = (await session.execute(
        select(User.id).where(User.email == email)
    )).scalar_one()

    redis = await get_redis()
    state = f"state-{email}"
    await redis.set(f"gh-oauth-state:{state}", f"{ws_id}:{user_id}", ex=300)
    r = await c.get(f"/api/v1/integrations/github/oauth-callback?code=c&state={state}")
    assert r.status_code == 303


async def test_import_creates_projects_with_repos_and_links(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            await _setup_connected(c, session, "import@example.com", monkeypatch)

            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "OpenClaw-as-a-Service",
                    "private": True,
                    "default_branch": "main",
                    "language": "Python",
                    "license": {"spdx_id": "MIT"},
                    "homepage": "https://butlr.cloud",
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-18T10:00:00Z",
                },
            })
            resp = await c.post(
                "/api/v1/integrations/github/import",
                json={"repos": [{"owner": "lenny", "name": "butlr"}]},
            )
    finally:
        clear_db_override()

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["status"] == "imported"
    assert body["results"][0]["slug"] == "butlr"

    project = (await session.execute(
        select(Project).where(Project.slug == "butlr")
    )).scalar_one()
    assert project.pitch == "OpenClaw-as-a-Service"

    repo = (await session.execute(
        select(ProjectRepo).where(ProjectRepo.project_id == project.id)
    )).scalar_one()
    assert repo.git_url == "https://github.com/lenny/butlr.git"
    assert repo.primary_lang == "Python"
    assert repo.license == "MIT"
```

**File:** `backend/tests/test_github_resync.py`

```python
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.main import app
from app.models import ProjectRepo
from tests._auth_helpers import clear_db_override, override_db, sign_in
from tests._github_helpers import patch_github

pytestmark = pytest.mark.integration


async def test_resync_updates_metadata(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_db(session)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://t", follow_redirects=False,
        ) as c:
            # Setup connection
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
            })
            await sign_in(c, session, "resync@example.com")
            me = (await c.get("/api/v1/me")).json()
            ws_slug = me["active_workspace"]["slug"]

            from app.models import User, Workspace
            ws_id = (await session.execute(
                select(Workspace.id).where(Workspace.slug == ws_slug)
            )).scalar_one()
            user_id = (await session.execute(
                select(User.id).where(User.email == "resync@example.com")
            )).scalar_one()

            redis = await get_redis()
            await redis.set("gh-oauth-state:s", f"{ws_id}:{user_id}", ex=300)
            await c.get("/api/v1/integrations/github/oauth-callback?code=c&state=s")

            # Create project with GitHub repo via import
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "v1",
                    "private": False,
                    "default_branch": "main",
                    "language": "Python",
                    "license": {"spdx_id": "MIT"},
                    "homepage": None,
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-18T10:00:00Z",
                },
            })
            await c.post(
                "/api/v1/integrations/github/import",
                json={"repos": [{"owner": "lenny", "name": "butlr"}]},
            )

            # Resync with updated metadata
            patch_github(monkeypatch, {
                "exchange_code": "ghp_fake",
                "me": {"login": "lenny"},
                "get_repo": {
                    "name": "butlr",
                    "owner": {"login": "lenny"},
                    "full_name": "lenny/butlr",
                    "description": "v2",
                    "private": False,
                    "default_branch": "develop",
                    "language": "Rust",
                    "license": {"spdx_id": "Apache-2.0"},
                    "homepage": None,
                    "clone_url": "https://github.com/lenny/butlr.git",
                    "pushed_at": "2026-04-19T10:00:00Z",
                },
            })
            resp = await c.post("/api/v1/projects/butlr/repo/resync")
    finally:
        clear_db_override()

    assert resp.status_code == 200

    repo = (await session.execute(
        select(ProjectRepo).where(ProjectRepo.git_url == "https://github.com/lenny/butlr.git")
    )).scalar_one()
    assert repo.default_branch == "develop"
    assert repo.primary_lang == "Rust"
    assert repo.license == "Apache-2.0"
```

Commit: `test(backend): github integration tests (OAuth + repos list + import + resync)`

---

## Phase 8 complete when

- [ ] 7 GitHub-related endpoints working.
- [ ] Ruff + mypy green.
- [ ] ~112 tests pass on staging (104 prior + 8 new).
- [ ] 7 commits on main (8.1–8.7).
