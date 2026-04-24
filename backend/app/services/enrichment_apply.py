"""Shared writer that applies an EnrichmentResult to a project.

Used by:
- GitHub repo import (app.api.v1.github_repos)
- MCP vibecell_sync_repo tool (app.mcp.handlers.write)

Idempotent: running twice on the same project with identical enrichment
data won't duplicate stack rows, tags, or overwrite existing infra unless
the new infra fields are non-null AND the existing field is null.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import (
    Project,
    ProjectInfra,
    ProjectStack,
    ProjectTag,
    StackItem,
    Tag,
)
from app.services.enrichment import EnrichmentResult


@dataclass
class ApplyStats:
    """Summary of what was written. Useful for telling the user what happened."""

    pitch_updated: bool = False
    stack_added: list[str] = None  # slugs that were newly linked
    tags_added: list[str] = None  # names that were newly linked
    infra_updated: bool = False

    def __post_init__(self) -> None:
        if self.stack_added is None:
            self.stack_added = []
        if self.tags_added is None:
            self.tags_added = []


async def apply_enrichment_to_project(
    db: AsyncSession,
    *,
    project: Project,
    workspace_id: str,
    enriched: EnrichmentResult,
    overwrite_pitch_if_thin: bool = True,
) -> ApplyStats:
    """Apply enrichment to a project.

    - pitch: set only if current is empty/short (<20 chars) AND overwrite_pitch_if_thin
    - tags: dedup across workspace; only links new ones
    - stack: dedup across global StackItem; only links new ones
    - infra: merges into ProjectInfra — per-field, only fills null fields
    """
    stats = ApplyStats()

    # --- Pitch ---
    if enriched.pitch:
        if overwrite_pitch_if_thin and (not project.pitch or len(project.pitch or "") < 20):
            project.pitch = enriched.pitch[:2000]
            stats.pitch_updated = True

    # --- Tags ---
    for tag_name in (enriched.tags or [])[:8]:
        if not tag_name:
            continue
        tag_name = tag_name.lower().strip()[:100]
        if not tag_name:
            continue
        existing_tag = (await db.execute(
            select(Tag).where(
                Tag.workspace_id == workspace_id,
                Tag.name == tag_name,
            )
        )).scalar_one_or_none()
        if existing_tag is None:
            existing_tag = Tag(id=new_ulid(), workspace_id=workspace_id, name=tag_name)
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
            stats.tags_added.append(tag_name)

    # --- Stack ---
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
            stats.stack_added.append(slug)

    # --- Infra (merge per-field; never clobber existing non-null values) ---
    if enriched.infra:
        existing_infra = (await db.execute(
            select(ProjectInfra).where(ProjectInfra.project_id == project.id)
        )).scalar_one_or_none()

        # Map from enrichment's loose keys to our model's columns. The enrichment
        # schema uses "framework" (meta) and "db" — we store "db" under db_host.
        field_map = {
            "server_alias": "server_alias",
            "db": "db_host",
            "dns_provider": "dns_provider",
            "cdn": "cdn",
            "object_storage": "object_storage",
        }

        if existing_infra is None:
            kwargs = {"project_id": project.id}
            for src_key, dest_col in field_map.items():
                val = enriched.infra.get(src_key)
                if val:
                    kwargs[dest_col] = str(val)[:255]
            if len(kwargs) > 1:  # more than just project_id
                db.add(ProjectInfra(**kwargs))
                stats.infra_updated = True
        else:
            for src_key, dest_col in field_map.items():
                if getattr(existing_infra, dest_col) is None:
                    val = enriched.infra.get(src_key)
                    if val:
                        setattr(existing_infra, dest_col, str(val)[:255])
                        stats.infra_updated = True

    return stats
