"""GitHub repos listing + bulk import into projects."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
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
        except Exception as e:
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
        except Exception as e:
            results.append(ImportResultItem(
                owner=item.owner, name=item.name, slug=desired,
                status="failed", detail=f"create: {e!s}",
            ))

    await db.commit()
    return ImportResponse(results=results)
