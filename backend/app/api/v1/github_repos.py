"""GitHub repos listing + bulk import into projects."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, require_auth
from app.models import Project, ProjectInfra, ProjectStack, StackItem
from app.schemas.integration import (
    GitHubRepoOut,
    ImportRequest,
    ImportResponse,
    ImportResultItem,
)
from app.services import github as github_svc
from app.services import integration as integ_svc
from app.services.enrichment import enrich_from_repo, fetch_repo_context
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


def _stack_slug(language: str) -> str:
    """Normalize a GitHub language name to a StackItem.slug (lowercase, hyphenated)."""
    import re
    s = re.sub(r"[^a-z0-9-]", "-", language.lower())
    return re.sub(r"-+", "-", s).strip("-") or "unknown"


@router.post("/import", response_model=ImportResponse)
async def bulk_import(
    body: ImportRequest,
    auth: AuthDep,
    db: DbDep,
) -> ImportResponse:
    from sqlalchemy import select

    from app.models import ProjectLink, ProjectRepo, Tag, ProjectTag

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
            # GitHub link (always) + Homepage (if set)
            if norm.get("html_url"):
                db.add(ProjectLink(
                    id=new_ulid(),
                    project_id=project.id,
                    kind="github",
                    label="GitHub",
                    url=norm["html_url"],
                ))
            if norm.get("homepage"):
                db.add(ProjectLink(
                    id=new_ulid(),
                    project_id=project.id,
                    kind="live",
                    label="Homepage",
                    url=norm["homepage"],
                ))
            # Language → StackItem (get or create) + ProjectStack
            lang = norm.get("language")
            if lang:
                lang_slug = _stack_slug(lang)
                stack_item = (await db.execute(
                    select(StackItem).where(StackItem.slug == lang_slug)
                )).scalar_one_or_none()
                if stack_item is None:
                    stack_item = StackItem(
                        id=new_ulid(),
                        slug=lang_slug,
                        name=lang,
                        kind="language",
                    )
                    db.add(stack_item)
                    await db.flush()
                db.add(ProjectStack(
                    project_id=project.id,
                    stack_item_id=stack_item.id,
                    role="language",
                ))
            # Topics → Tags (get or create per workspace) + ProjectTag
            for topic in (norm.get("topics") or [])[:20]:
                tag = (await db.execute(
                    select(Tag).where(
                        Tag.workspace_id == auth.active_workspace_id,
                        Tag.name == topic,
                    )
                )).scalar_one_or_none()
                if tag is None:
                    tag = Tag(
                        id=new_ulid(),
                        workspace_id=auth.active_workspace_id,
                        name=topic,
                    )
                    db.add(tag)
                    await db.flush()
                db.add(ProjectTag(project_id=project.id, tag_id=tag.id))

            # AI enrichment — Spec 3.6
            try:
                fetched = await fetch_repo_context(
                    token, item.owner, item.name, norm["default_branch"],
                )
                enriched = await enrich_from_repo(
                    name=norm["name"],
                    description=norm.get("description"),
                    language=norm.get("language"),
                    topics=norm.get("topics") or [],
                    fetched_files=fetched,
                )

                # Apply pitch if LLM produced a better one AND project currently has none/thin
                if enriched.pitch and (not project.pitch or len(project.pitch or "") < 20):
                    project.pitch = enriched.pitch[:2000]

                # Apply tags (dedupe against existing topic-derived tags)
                for tag_name in (enriched.tags or [])[:8]:
                    if not tag_name:
                        continue
                    tag_name = tag_name.lower()[:100]
                    existing_tag = (await db.execute(
                        select(Tag).where(
                            Tag.workspace_id == auth.active_workspace_id,
                            Tag.name == tag_name,
                        )
                    )).scalar_one_or_none()
                    if existing_tag is None:
                        existing_tag = Tag(
                            id=new_ulid(),
                            workspace_id=auth.active_workspace_id,
                            name=tag_name,
                        )
                        db.add(existing_tag)
                        await db.flush()
                    already_linked = (await db.execute(
                        select(ProjectTag).where(
                            ProjectTag.project_id == project.id,
                            ProjectTag.tag_id == existing_tag.id,
                        )
                    )).scalar_one_or_none()
                    if not already_linked:
                        db.add(ProjectTag(project_id=project.id, tag_id=existing_tag.id))

                # Apply stack items (dedupe)
                for si in (enriched.stack or [])[:10]:
                    slug = (si.get("slug") or "").lower().strip()
                    name_ = si.get("name") or slug.title()
                    kind = si.get("kind") or "library"
                    role = si.get("role")
                    if not slug:
                        continue
                    existing_si = (await db.execute(
                        select(StackItem).where(StackItem.slug == slug)
                    )).scalar_one_or_none()
                    if existing_si is None:
                        existing_si = StackItem(
                            id=new_ulid(),
                            slug=slug[:100],
                            name=name_[:200],
                            kind=kind[:30],
                        )
                        db.add(existing_si)
                        await db.flush()
                    already_linked_s = (await db.execute(
                        select(ProjectStack).where(
                            ProjectStack.project_id == project.id,
                            ProjectStack.stack_item_id == existing_si.id,
                        )
                    )).scalar_one_or_none()
                    if not already_linked_s:
                        db.add(ProjectStack(
                            project_id=project.id,
                            stack_item_id=existing_si.id,
                            role=role[:20] if role else None,
                        ))

                # Apply infra hints (only if none recorded yet)
                if enriched.infra:
                    existing_infra = (await db.execute(
                        select(ProjectInfra).where(ProjectInfra.project_id == project.id)
                    )).scalar_one_or_none()
                    if existing_infra is None:
                        db.add(ProjectInfra(
                            project_id=project.id,
                            server_alias=enriched.infra.get("server_alias"),
                            domain_primary=None,
                            db_host=enriched.infra.get("db"),
                            dns_provider=enriched.infra.get("dns_provider"),
                            cdn=enriched.infra.get("cdn"),
                            object_storage=enriched.infra.get("object_storage"),
                        ))
            except Exception as enrich_err:
                import logging
                logging.getLogger(__name__).warning(
                    "enrichment error (non-fatal) for %s/%s: %s",
                    item.owner, item.name, enrich_err,
                )

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
