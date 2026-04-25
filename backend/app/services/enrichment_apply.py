"""Shared writer that applies an EnrichmentResult to a project.

Used by:
- GitHub repo import (app.api.v1.github_repos)
- MCP vibecell_sync_repo tool (app.mcp.handlers.write)

Idempotent: running twice on the same project with identical enrichment
data won't duplicate stack rows, tags, environments, commands, or links,
and won't overwrite existing non-null infra fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models import (
    Project,
    ProjectCommand,
    ProjectEnvironment,
    ProjectInfra,
    ProjectLink,
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
    emoji_updated: bool = False
    infra_updated: bool = False
    stack_added: list[str] = field(default_factory=list)
    tags_added: list[str] = field(default_factory=list)
    environments_added: list[str] = field(default_factory=list)  # kinds added
    commands_added: list[str] = field(default_factory=list)      # labels added
    links_added: list[str] = field(default_factory=list)         # (kind:label) added


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
    - emoji: set only if current is missing or the default "📦"
    - tags: dedup across workspace; only links new ones
    - stack: dedup across global StackItem; only links new ones
    - infra: merges into ProjectInfra — per-field, only fills null fields
    - environments: dedup by `kind`; inserts only kinds not yet present
    - commands: dedup by `label` (case-insensitive); inserts only new labels
    - extra_links: dedup by `url`; inserts only new URLs
    """
    stats = ApplyStats()

    # --- Pitch ---
    if enriched.pitch and overwrite_pitch_if_thin and (not project.pitch or len(project.pitch or "") < 20):
        project.pitch = enriched.pitch[:2000]
        stats.pitch_updated = True

    # --- Emoji --- (overwrite only the default box)
    if enriched.emoji and (not project.emoji or project.emoji == "📦"):
        # Cap to 2 chars (most emojis are 1-2 codepoints; some flags are longer but model rarely returns those).
        project.emoji = enriched.emoji[:16]
        stats.emoji_updated = True

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

        # Map enrichment's loose keys to our model's columns.
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

    # --- Environments (dedup by kind) ---
    existing_env_kinds = {
        row.kind for row in (await db.execute(
            select(ProjectEnvironment).where(ProjectEnvironment.project_id == project.id)
        )).scalars().all()
    }
    for env in (enriched.environments or [])[:3]:
        kind = (env.get("kind") or "").strip()
        url = (env.get("url") or "").strip()
        if kind not in {"local", "staging", "prod"} or not url:
            continue
        if kind in existing_env_kinds:
            continue
        db.add(ProjectEnvironment(
            id=new_ulid(),
            project_id=project.id,
            kind=kind,
            url=str(url)[:2000],
            env_template_path=(env.get("env_template_path") or None),
        ))
        existing_env_kinds.add(kind)
        stats.environments_added.append(kind)

    # --- Commands (dedup by label, case-insensitive) ---
    existing_cmd_labels = {
        (row.label or "").lower()
        for row in (await db.execute(
            select(ProjectCommand).where(ProjectCommand.project_id == project.id)
        )).scalars().all()
    }
    for cmd in (enriched.commands or [])[:8]:
        label = (cmd.get("label") or "").strip()
        command = (cmd.get("command") or "").strip()
        run_in = cmd.get("run_in") or "terminal"
        if not label or not command:
            continue
        if label.lower() in existing_cmd_labels:
            continue
        db.add(ProjectCommand(
            id=new_ulid(),
            project_id=project.id,
            label=label[:200],
            command=command[:4000],
            run_in=run_in if run_in in {"terminal", "browser"} else "terminal",
            confirm_required=0,  # LLM-suggested commands shouldn't gate on confirm by default
        ))
        existing_cmd_labels.add(label.lower())
        stats.commands_added.append(label)

    # --- Extra links (dedup by URL) ---
    existing_link_urls = {
        row.url for row in (await db.execute(
            select(ProjectLink).where(ProjectLink.project_id == project.id)
        )).scalars().all()
    }
    for lnk in (enriched.extra_links or [])[:4]:
        url = (lnk.get("url") or "").strip()
        label = (lnk.get("label") or "").strip()
        kind = lnk.get("kind") or "other"
        if not url or not label:
            continue
        if url in existing_link_urls:
            continue
        db.add(ProjectLink(
            id=new_ulid(),
            project_id=project.id,
            kind=kind[:50],
            label=label[:200],
            url=url[:2000],
        ))
        existing_link_urls.add(url)
        stats.links_added.append(f"{kind}:{label}")

    return stats
