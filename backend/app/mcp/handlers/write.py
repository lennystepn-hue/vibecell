"""MCP write handlers — wired to backend services (Task 2.6)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.mcp.auth import MCPContext
from app.mcp.handlers.read import _get_active_project, _resolve_project
from app.services import secret as secret_svc

_VALID_STATUSES = {"idea", "building", "live", "paused", "shipped", "archived", "dead"}


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

def _detect_kind(value: str) -> str:
    v = value.strip()
    if v.startswith("op://"):
        return "op"
    if v.startswith("bw://"):
        return "bw"
    if v.startswith("ssh-agent://"):
        return "ssh_agent"
    if v.startswith("env://"):
        return "env_path"
    if v.startswith("keychain://"):
        return "keychain"
    return "inline_encrypted"


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

async def handle_switch(args, ctx: MCPContext) -> str:
    """Switch the active project to args.slug."""
    from sqlalchemy import select

    from app.models import Project
    from app.services.project import set_active_project

    project = (await ctx.db.execute(
        select(Project).where(
            Project.workspace_id == ctx.workspace_id,
            Project.slug == args.slug,
        )
    )).scalar_one_or_none()
    if not project:
        raise RuntimeError(f"Project {args.slug!r} not found in workspace")
    await set_active_project(
        ctx.db,
        workspace_id=ctx.workspace_id,
        user_id=ctx.user_id,
        project=project,
    )
    return json.dumps({"active_slug": args.slug})


def _auto_focus_from_summary(summary: str, cap: int = 280) -> str:
    """Derive a tidy current_focus snippet from a session summary.

    Takes the first sentence (up to the first period followed by space/newline/EOF),
    strips whitespace, and caps length. Falls back to truncating the whole summary
    if no sentence boundary is found.
    """
    s = (summary or "").strip()
    if not s:
        return ""
    # Find first ". " or "\n" — whichever comes first
    candidates = [i for i in (s.find(". "), s.find("\n")) if i > 0]
    cut = min(candidates) if candidates else -1
    head = s[:cut].strip() if cut > 0 else s
    if len(head) > cap:
        head = head[: cap - 1].rstrip() + "…"
    return head


async def handle_log_session(args, ctx: MCPContext) -> str:
    """Log a coding session and sync project context.

    Also updates the active project's current_focus (auto-derived from the
    summary unless args.current_focus is explicitly set) and next_step (if
    args.next_step is set). This keeps the session log and the project-level
    "what am I working on" view in sync without a second tool call.
    """
    from app.services import project_children as children_svc
    from app.services.session_svc import create_session

    project = await _get_active_project(ctx)
    now = datetime.now(UTC)
    session = await create_session(
        ctx.db,
        project=project,
        started_at=now,
        ended_at=now,
        summary=args.summary,
        files_touched=getattr(args, "files_touched", []) or [],
        commits=getattr(args, "commits", []) or [],
        next_step=getattr(args, "next_step", None),
        source="skill",
    )

    # Auto-sync project context so current_focus never goes stale between sessions.
    explicit_focus = getattr(args, "current_focus", None)
    new_focus = explicit_focus if explicit_focus is not None else _auto_focus_from_summary(args.summary)
    ctx_updates: dict[str, str] = {}
    if new_focus:
        ctx_updates["current_focus"] = new_focus
    next_step = getattr(args, "next_step", None)
    if next_step:
        ctx_updates["next_step"] = next_step
    if ctx_updates:
        await children_svc.upsert_context(ctx.db, project, **ctx_updates)

    return json.dumps({
        "id": session.id,
        "summary": session.summary,
        "next_step": session.next_step,
        "current_focus": ctx_updates.get("current_focus"),
    })


async def handle_update_context(args, ctx: MCPContext) -> str:
    """Patch the active project's context fields."""
    from app.services import project_children as children_svc

    project = await _get_active_project(ctx)
    fields = {
        k: v for k, v in {
            "current_focus": getattr(args, "current_focus", None),
            "next_step": getattr(args, "next_step", None),
            "user_wants": getattr(args, "user_wants", None),
            "open_questions": getattr(args, "open_questions", None),
            "known_issues": getattr(args, "known_issues", None),
            "blocked_by": getattr(args, "blocked_by", None),
        }.items()
        if v is not None
    }
    ctx_row = await children_svc.upsert_context(ctx.db, project, **fields)
    return json.dumps({
        "current_focus": ctx_row.current_focus,
        "next_step": ctx_row.next_step,
        "user_wants": ctx_row.user_wants,
        "open_questions": ctx_row.open_questions,
        "known_issues": ctx_row.known_issues,
        "blocked_by": ctx_row.blocked_by,
    })


async def handle_set_focus(args, ctx: MCPContext) -> str:
    """One-shot focus + next_step update — the daily-driver context tool.

    Designed for friction-free use: 1-2 args, dedup-safe (idempotent), and
    deliberately narrow so Claude doesn't have to think about which fields
    to pass. SKILL.md tells Claude to fire this on every topic shift.
    """
    from app.services import project_children as children_svc

    project = await _resolve_project(args, ctx)
    fields: dict[str, str] = {"current_focus": args.current_focus.strip()}
    next_step = (getattr(args, "next_step", None) or "").strip()
    if next_step:
        fields["next_step"] = next_step
    ctx_row = await children_svc.upsert_context(ctx.db, project, **fields)
    return json.dumps({
        "project_slug": project.slug,
        "current_focus": ctx_row.current_focus,
        "next_step": ctx_row.next_step,
    })


async def handle_decision(args, ctx: MCPContext) -> str:
    """Record an ADR-lite decision on the active project."""
    from app.services.decision_svc import create_decision

    project = await _get_active_project(ctx)
    decision = await create_decision(
        ctx.db,
        project=project,
        title=args.title,
        decision=args.decision,
        context=getattr(args, "context", None),
        consequences=getattr(args, "consequences", None),
        reconsider_if=getattr(args, "reconsider_if", None),
    )
    return json.dumps({"id": decision.id, "title": decision.title})


async def handle_idea(args, ctx: MCPContext) -> str:
    """Capture an idea. Routes to workspace inbox if no project given."""
    from app.services.idea_svc import create_idea

    project_slug: str | None = getattr(args, "project", None)
    project_id: str | None = None

    if project_slug:
        project = await _resolve_project(args, ctx)
        project_id = project.id

    idea = await create_idea(
        ctx.db,
        workspace_id=ctx.workspace_id,
        body=args.body,
        project_id=project_id,
        source="skill",
    )
    return json.dumps({
        "id": idea.id,
        "body": idea.body,
        "project_id": idea.project_id,
    })


async def handle_note_append(args, ctx: MCPContext) -> str:
    """Append a markdown block to the active project's notes."""
    from app.services.note_svc import get_note, upsert_note

    project = await _get_active_project(ctx)
    existing = await get_note(ctx.db, project=project)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    new_block = f"\n\n---\n\n{timestamp}\n{args.markdown}"

    if existing and existing.markdown:
        updated_text = existing.markdown + new_block
    else:
        updated_text = args.markdown

    note = await upsert_note(ctx.db, project=project, markdown=updated_text)
    return json.dumps({"notes": note.markdown})


async def handle_ship(args, ctx: MCPContext) -> str:
    """Record a ship event (+ lifecycle row) for the active project."""
    from app.services.ship_svc import create_ship

    project = await _get_active_project(ctx)
    ship = await create_ship(
        ctx.db,
        project=project,
        version=getattr(args, "version", None),
        summary=getattr(args, "summary", None),
        changelog_md=getattr(args, "changelog_md", None),
    )
    return json.dumps({"id": ship.id, "version": ship.version})


async def handle_status(args, ctx: MCPContext) -> str:
    """Set the active project's status."""
    from app.services.project import update_project

    status: str = args.status
    if status not in _VALID_STATUSES:
        raise RuntimeError(
            f"Invalid status {status!r}. Must be one of: {', '.join(sorted(_VALID_STATUSES))}"
        )

    project = await _get_active_project(ctx)
    await update_project(ctx.db, project=project, status=status)
    return json.dumps({"slug": project.slug, "status": args.status})


async def handle_secret_set(args, ctx: MCPContext) -> str:
    """Upsert a secret for the project. Auto-detects kind from value prefix."""
    # Resolve project (args.project is a slug; falls back to active)

    from app.mcp.handlers.read import _get_active_project as _get_active
    from app.services.project import get_project

    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active(ctx)

    kind = _detect_kind(args.value)

    # Upsert: if label already exists, remove it first
    existing = await secret_svc.get_secret(ctx.db, project, args.label)
    if existing is not None:
        await secret_svc.remove_secret(ctx.db, project, args.label)

    ref = await secret_svc.add_secret(
        ctx.db,
        project,
        label=args.label,
        kind=kind,
        reference=args.value,
        workspace_id=ctx.workspace_id,
    )

    # ONLY return metadata — never the value
    return json.dumps({
        "ok": True,
        "label": ref.label,
        "kind": kind,
        "project": project.slug,
        "note": (
            "Value is encrypted at rest (inline) or stored as reference (op/bw/ssh)."
            if kind == "inline_encrypted"
            else "Reference stored; value never touches Vibecell."
        ),
    })


async def handle_secret_rm(args, ctx: MCPContext) -> str:
    """Remove a secret label from a project."""
    from app.services.project import get_project

    project_slug: str | None = getattr(args, "project", None)
    if project_slug:
        project = await get_project(ctx.db, workspace_id=ctx.workspace_id, slug=project_slug)
    else:
        project = await _get_active_project(ctx)

    await secret_svc.remove_secret(ctx.db, project, args.label)
    return json.dumps({"ok": True, "label": args.label, "project": project.slug})


# ---------------------------------------------------------------------------
# TODO handlers
# ---------------------------------------------------------------------------

def _todo_out(row) -> dict:
    return {
        "id": row.id,
        "batch": row.batch,
        "title": row.title,
        "body": row.body,
        "status": row.status,
        "position": row.position,
        "completed_by": row.completed_by,
        "completion_note": row.completion_note,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def handle_todo_add(args, ctx: MCPContext) -> str:
    """Add a single todo to a project."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.create_todo(
        ctx.db,
        project=project,
        title=args.title,
        body=getattr(args, "body", None),
        batch=getattr(args, "batch", None),
    )
    return json.dumps(_todo_out(row))


async def handle_todo_batch_add(args, ctx: MCPContext) -> str:
    """Add many todos at once under one batch label."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    items = [{"title": t} for t in args.titles]
    rows = await todo_svc.create_batch(
        ctx.db, project=project, batch=args.batch, items=items,
    )
    return json.dumps({
        "batch": args.batch,
        "count": len(rows),
        "todos": [_todo_out(r) for r in rows],
    })


async def handle_todo_start(args, ctx: MCPContext) -> str:
    """Mark a todo as in_progress — lights up the 'claude is on this' indicator."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.start_todo(ctx.db, project=project, todo_id=args.todo_id)
    return json.dumps(_todo_out(row))


async def handle_todo_complete(args, ctx: MCPContext) -> str:
    """Mark a todo as done (completed_by=claude). Pass completion_note describing what was built."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    row = await todo_svc.complete_todo(
        ctx.db,
        project=project,
        todo_id=args.todo_id,
        completed_by="claude",
        completion_note=getattr(args, "completion_note", None),
    )
    return json.dumps(_todo_out(row))


async def handle_todo_match(args, ctx: MCPContext) -> str:
    """Fuzzy-match a description against open todos. Optionally auto-complete the best match."""
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    best = await todo_svc.match_open_todo(
        ctx.db, project=project, description=args.description,
    )
    if best is None:
        return json.dumps({"matched": None, "note": "no open todo matched that description"})
    if getattr(args, "auto_complete", False):
        best = await todo_svc.complete_todo(
            ctx.db,
            project=project,
            todo_id=best.id,
            completed_by="claude",
            completion_note=args.description,
        )
    return json.dumps({"matched": _todo_out(best)})


# ---------------------------------------------------------------------------
# AI (BYOK) handlers — shared logic with /api/v1/projects/:slug/ai/*
# ---------------------------------------------------------------------------

async def _ai_project_context(db, project) -> str:
    """Build the same context blob the REST endpoints use."""
    from sqlalchemy import select

    from app.models import ProjectContext as PCtx

    ctx_row = (await db.execute(
        select(PCtx).where(PCtx.project_id == project.id)
    )).scalar_one_or_none()
    pitch = project.pitch or "(no pitch)"
    focus = ctx_row.current_focus if ctx_row else "(no current focus)"
    next_step = ctx_row.next_step if ctx_row else "(no next step)"
    oq = ctx_row.open_questions if ctx_row else []
    return (
        f"Project: {project.name} ({project.slug})\n"
        f"Pitch: {pitch}\n"
        f"Current focus: {focus}\n"
        f"Next step: {next_step}\n"
        f"Open questions: {', '.join(oq) if oq else '(none)'}\n"
    )


async def handle_ai_plan_todos(args, ctx: MCPContext) -> str:
    """Break a goal into a batch of todos using the user's Anthropic key, persist them."""
    from app.services import ai as ai_svc
    from app.services import todo_svc

    project = await _resolve_project(args, ctx)
    context = await _ai_project_context(ctx.db, project)
    try:
        batch, titles, meta = await ai_svc.plan_todos(
            ctx.db, project=project, workspace_id=ctx.workspace_id,
            goal=args.goal, context_brief=context,
        )
    except ai_svc.AIConfigError as exc:
        return json.dumps({"error": "no_ai_key", "message": str(exc)})

    todo_ids: list[str] = []
    if getattr(args, "commit", True) and titles:
        rows = await todo_svc.create_batch(
            ctx.db, project=project, batch=batch,
            items=[{"title": t} for t in titles],
        )
        todo_ids = [r.id for r in rows]
    return json.dumps({
        "batch": batch, "titles": titles, "todo_ids": todo_ids, "meta": meta,
    })


async def handle_ai_launch_copy(args, ctx: MCPContext) -> str:
    """Generate platform-specific launch posts for a ship."""
    from sqlalchemy import select

    from app.models import Ship
    from app.services import ai as ai_svc

    project = await _resolve_project(args, ctx)

    ship = None
    if getattr(args, "ship_id", None):
        ship = (await ctx.db.execute(
            select(Ship).where(
                Ship.id == args.ship_id, Ship.project_id == project.id,
            )
        )).scalar_one_or_none()
    if ship is None:
        ship = (await ctx.db.execute(
            select(Ship).where(Ship.project_id == project.id)
            .order_by(Ship.shipped_at.desc()).limit(1)
        )).scalar_one_or_none()
    if ship is None:
        return json.dumps({
            "error": "no_ship", "message": "No ship events yet — call vibecell.ship first.",
        })

    context = await _ai_project_context(ctx.db, project)
    ship_blob = (
        f"{context}\nShip version: {ship.version or '?'}\n"
        f"Ship summary: {ship.summary or '(empty)'}\n"
        f"Changelog:\n{ship.changelog_md or '(empty)'}\n"
    )
    try:
        posts, meta = await ai_svc.launch_copy(
            ctx.db, project=project, workspace_id=ctx.workspace_id,
            ship_context=ship_blob,
            platforms=getattr(args, "platforms", ["twitter_x", "linkedin", "indiehackers", "product_hunt"]),
        )
    except ai_svc.AIConfigError as exc:
        return json.dumps({"error": "no_ai_key", "message": str(exc)})

    return json.dumps({"ship_id": ship.id, "posts": posts, "meta": meta})


async def handle_ai_retro(args, ctx: MCPContext) -> str:
    """Generate a markdown retro covering activity since the last ship."""
    from sqlalchemy import select

    from app.models import Decision, Session, Ship
    from app.services import ai as ai_svc

    project = await _resolve_project(args, ctx)

    latest_ship = (await ctx.db.execute(
        select(Ship).where(Ship.project_id == project.id)
        .order_by(Ship.shipped_at.desc()).limit(1)
    )).scalar_one_or_none()
    cutoff = latest_ship.shipped_at if latest_ship else None

    session_stmt = select(Session).where(Session.project_id == project.id)
    decision_stmt = select(Decision).where(Decision.project_id == project.id)
    if cutoff is not None:
        session_stmt = session_stmt.where(Session.started_at > cutoff)
        decision_stmt = decision_stmt.where(Decision.created_at > cutoff)

    sessions = (await ctx.db.execute(
        session_stmt.order_by(Session.started_at.asc())
    )).scalars().all()
    decisions = (await ctx.db.execute(
        decision_stmt.order_by(Decision.created_at.asc())
    )).scalars().all()

    lines = []
    if latest_ship:
        lines.append(f"Previous ship: {latest_ship.version or '?'} — {latest_ship.summary or ''}")
    else:
        lines.append("No previous ship; retro covers all activity to date.")
    lines.append("")
    lines.append(f"{len(sessions)} session(s):")
    for s in sessions[-20:]:
        lines.append(f"- {s.summary or '(empty)'}")
    lines.append("")
    lines.append(f"{len(decisions)} decision(s):")
    for d in decisions[-15:]:
        lines.append(f"- {d.title}: {d.decision[:200]}")
    events_summary = "\n".join(lines)

    try:
        md, meta = await ai_svc.retro(
            ctx.db, project=project, workspace_id=ctx.workspace_id,
            events_summary=events_summary,
        )
    except ai_svc.AIConfigError as exc:
        return json.dumps({"error": "no_ai_key", "message": str(exc)})
    return json.dumps({"markdown": md, "meta": meta})


async def handle_ai_resume_brief(args, ctx: MCPContext) -> str:
    """Generate the funny 'where the fuck was I' morning brief."""
    from sqlalchemy import select

    from app.models import Decision, Session
    from app.services import ai as ai_svc

    project = await _resolve_project(args, ctx)
    context = await _ai_project_context(ctx.db, project)

    last = (await ctx.db.execute(
        select(Session).where(Session.project_id == project.id)
        .order_by(Session.started_at.desc()).limit(1)
    )).scalar_one_or_none()
    last_blob = (
        f"Last session at {last.started_at.isoformat() if last and last.started_at else '?'}: "
        f"{last.summary if last else '(no sessions yet)'}\n"
        f"Next step: {last.next_step if last else '(none)'}"
    )

    decisions = (await ctx.db.execute(
        select(Decision).where(Decision.project_id == project.id)
        .order_by(Decision.created_at.desc()).limit(3)
    )).scalars().all()
    d_blob = "\n".join(f"- {d.title}: {d.decision[:140]}" for d in decisions) or "(no decisions)"

    blob = f"{context}\nLAST SESSION:\n{last_blob}\n\nRECENT DECISIONS:\n{d_blob}\n"
    try:
        text, meta = await ai_svc.resume_brief(
            ctx.db, project=project, workspace_id=ctx.workspace_id,
            context_blob=blob,
        )
    except ai_svc.AIConfigError as exc:
        return json.dumps({"error": "no_ai_key", "message": str(exc)})
    return json.dumps({"brief": text, "meta": meta})


# ---------------------------------------------------------------------------
# Repo sync — called from SKILL.md session-start hook for local repos.
# ---------------------------------------------------------------------------

async def handle_sync_repo(args, ctx: MCPContext) -> str:
    """Scan a local repo: persist local_path, enrich stack/infra/tags/pitch,
    store fingerprints so we can detect drift on the next session.

    The MCP server runs on vibecell.dev and can't read the user's filesystem.
    So Claude reads the manifest files locally (Read tool) and passes their
    content in `manifests` — {path: content}. We compute the fingerprint
    server-side + call enrichment on the same content.

    Smart behavior:
    - First time (never_scanned OR stack+infra both empty) → full enrich
    - Subsequent call but no drift → no-op, just touch scanned_at
    - Subsequent call with drift → re-enrich (refresh stack/infra/tags)
    """
    from sqlalchemy import select

    from app.models import ProjectRepo
    from app.models.project import ProjectContext
    from app.services import project_children as children_svc
    from app.services.enrichment import enrich_from_repo
    from app.services.enrichment_apply import apply_enrichment_to_project
    from app.services.env_fingerprint import (
        build_fingerprint,
        compute_drift,
    )

    project = await _resolve_project(args, ctx)
    manifests: dict[str, str] = dict(getattr(args, "manifests", {}) or {})
    local_path: str | None = getattr(args, "local_path", None)
    force: bool = bool(getattr(args, "force", False))

    # --- 1. Persist local_path on the monorepo/first ProjectRepo row ---
    repo = (await ctx.db.execute(
        select(ProjectRepo).where(ProjectRepo.project_id == project.id).limit(1)
    )).scalar_one_or_none()
    if repo is None:
        # No repo row yet — create a bare one so local_path has somewhere to live.
        from app.core.ulid import new_ulid
        repo = ProjectRepo(
            id=new_ulid(),
            project_id=project.id,
            role="monorepo",
            local_path=local_path,
        )
        ctx.db.add(repo)
        await ctx.db.flush()
    elif local_path and repo.local_path != local_path:
        repo.local_path = local_path

    # --- 2. Load / create ProjectContext so we can read stored fingerprint ---
    pctx = (await ctx.db.execute(
        select(ProjectContext).where(ProjectContext.project_id == project.id)
    )).scalar_one_or_none()
    if pctx is None:
        pctx = ProjectContext(project_id=project.id)
        ctx.db.add(pctx)
        await ctx.db.flush()

    stored_fp = pctx.env_fingerprint or {}

    # --- 3. Compute drift BEFORE re-enriching ---
    drift = compute_drift(stored_fp, manifests)

    # --- 4. Decide whether to enrich ---
    # Count existing enrichment signals to know if project is "naked".
    existing_stack = await children_svc.list_stack(ctx.db, project)
    existing_infra = await children_svc.get_infra(ctx.db, project)
    naked = (not existing_stack) and (existing_infra is None)

    should_enrich = force or drift.never_scanned or drift.drifted or naked

    mode = "no_change"
    stats = None

    if should_enrich and manifests:
        # Primary language hint: look for existing StackItem tagged kind=language.
        primary_lang = None
        for si, _ps in existing_stack:
            if si.kind == "language":
                primary_lang = si.name
                break
        if not primary_lang:
            primary_lang = (repo.primary_lang if repo else None)

        try:
            # Cap manifest content before shipping to the LLM.
            capped = {p: (c[:8000] if c else "") for p, c in manifests.items() if c}
            enriched = await enrich_from_repo(
                name=project.name,
                description=project.pitch,
                language=primary_lang,
                topics=[],  # existing tags are already persisted
                fetched_files=capped,
            )
            stats = await apply_enrichment_to_project(
                ctx.db,
                project=project,
                workspace_id=ctx.workspace_id,
                enriched=enriched,
            )
            mode = "initial_scan" if (drift.never_scanned or naked) else "drift_refresh"
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("sync_repo enrichment failed: %s", e)
            mode = "enrich_failed"

    # --- 5. Always update the fingerprint (even on no-op — refreshes scanned_at) ---
    if manifests:
        pctx.env_fingerprint = build_fingerprint(manifests, local_path=local_path)

    return json.dumps({
        "mode": mode,
        "drift": {
            "never_scanned": drift.never_scanned,
            "drifted": drift.drifted,
            "changed_files": drift.changed_files,
            "new_files": drift.new_files,
            "removed_files": drift.removed_files,
            "last_scanned": drift.last_scanned,
        },
        "enrichment": (
            {
                "pitch_updated": stats.pitch_updated,
                "stack_added": stats.stack_added,
                "tags_added": stats.tags_added,
                "infra_updated": stats.infra_updated,
            }
            if stats
            else None
        ),
        "project": {
            "slug": project.slug,
            "local_path": repo.local_path if repo else None,
        },
        "fingerprinted_files": sorted((pctx.env_fingerprint or {}).get("files", {}).keys()),
    })


# ---------------------------------------------------------------------------
# Project creation — the "sexy" flow: Claude helps the user concept a new
# project, then spawns it in Vibecell with one call. Accepts the full
# enrichment shape so the dashboard is populated from the first paint.
# ---------------------------------------------------------------------------

def _derive_slug(name: str, taken: set[str]) -> str:
    """Slugify name to [a-z0-9-], ensure uniqueness with numeric suffix."""
    import re

    clean = re.sub(r"[^a-z0-9-]", "-", (name or "").lower())
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


async def handle_create_project(args, ctx: MCPContext) -> str:
    """Create a new project + populate it with everything Claude gathered.

    This is the one-shot project spawner. After brainstorming a concept with
    the user, Claude calls this with as much structured info as it has
    (name + pitch at minimum; stack/tags/envs/commands/links optionally) and
    Vibecell provisions the full project page.

    - Auto-derives slug from name if omitted.
    - Auto-creates the group by name if `group` is given and doesn't exist.
    - Applies the same idempotent enrichment-writer used by GitHub import
      and sync_repo, so stack/tags/infra/envs/commands/links all go through
      the same dedup'd path.
    - Switches the active project to the new one by default (controllable
      via `switch_to_active: false`).
    """
    from sqlalchemy import select

    from app.core.ulid import new_ulid
    from app.models import (
        Project,
        ProjectGroup,
        ProjectLink,
        ProjectRepo,
    )
    from app.services.enrichment import EnrichmentResult
    from app.services.enrichment_apply import apply_enrichment_to_project
    from app.services.project import create_project, set_active_project

    name: str = (getattr(args, "name", "") or "").strip()
    if not name:
        raise RuntimeError("name is required")

    # --- Resolve unique slug ---
    requested_slug = (getattr(args, "slug", "") or "").strip().lower()
    existing_slugs = set(
        (await ctx.db.execute(
            select(Project.slug).where(Project.workspace_id == ctx.workspace_id)
        )).scalars()
    )
    slug = requested_slug if requested_slug and requested_slug not in existing_slugs else _derive_slug(name, existing_slugs)

    # --- Resolve / create group ---
    group_id: str | None = None
    group_input = (getattr(args, "group", "") or "").strip()
    if group_input:
        # Try by id first, then by exact name, then create new.
        grp = (await ctx.db.execute(
            select(ProjectGroup).where(
                ProjectGroup.workspace_id == ctx.workspace_id,
                (ProjectGroup.id == group_input) | (ProjectGroup.name == group_input),
            )
        )).scalar_one_or_none()
        if grp is None:
            grp = ProjectGroup(
                id=new_ulid(),
                workspace_id=ctx.workspace_id,
                name=group_input[:100],
                color=None,
            )
            ctx.db.add(grp)
            await ctx.db.flush()
        group_id = grp.id

    # --- Create project row ---
    status = getattr(args, "status", None) or "idea"
    if status not in _VALID_STATUSES:
        status = "idea"
    pitch = (getattr(args, "pitch", "") or "").strip() or None
    emoji = (getattr(args, "emoji", "") or "").strip() or None

    project = await create_project(
        ctx.db,
        workspace_id=ctx.workspace_id,
        slug=slug,
        name=name[:200],
        emoji=emoji,
        pitch=pitch,
        status=status,
    )
    if group_id:
        project.group_id = group_id

    # --- Optional GitHub URL → ProjectRepo + ProjectLink ---
    github_url = (getattr(args, "github_url", "") or "").strip()
    if github_url:
        ctx.db.add(ProjectRepo(
            id=new_ulid(),
            project_id=project.id,
            role="monorepo",
            git_url=github_url,
            default_branch="main",
        ))
        ctx.db.add(ProjectLink(
            id=new_ulid(),
            project_id=project.id,
            kind="github",
            label="GitHub",
            url=github_url,
        ))

    await ctx.db.flush()

    # --- Feed everything else through the shared enrichment writer ---
    # Convert the tool args into an EnrichmentResult; writer dedups + fills infra.
    enriched = EnrichmentResult(
        pitch=pitch,
        emoji=emoji,
        tags=list(getattr(args, "tags", None) or []),
        stack=list(getattr(args, "stack", None) or []),
        infra=dict(getattr(args, "infra", None) or {}),
        environments=list(getattr(args, "environments", None) or []),
        commands=list(getattr(args, "commands", None) or []),
        extra_links=list(getattr(args, "links", None) or []),
    )
    stats = await apply_enrichment_to_project(
        ctx.db,
        project=project,
        workspace_id=ctx.workspace_id,
        enriched=enriched,
        overwrite_pitch_if_thin=False,  # we already set pitch on the create
    )

    # --- Set as active project by default ---
    switch_to_active = getattr(args, "switch_to_active", True)
    if switch_to_active:
        await set_active_project(
            ctx.db,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user_id,
            project=project,
        )

    return json.dumps({
        "id": project.id,
        "slug": project.slug,
        "name": project.name,
        "status": project.status,
        "url": f"https://vibecell.dev/p/{project.slug}",
        "active": bool(switch_to_active),
        "stats": {
            "tags_added": stats.tags_added,
            "stack_added": stats.stack_added,
            "infra_updated": stats.infra_updated,
            "environments_added": stats.environments_added,
            "commands_added": stats.commands_added,
            "links_added": stats.links_added,
        },
    })


# ---------------------------------------------------------------------------
# Incremental project-metadata writers — after a project exists, let Claude
# add environments / links / commands one at a time without going through
# the full enrichment apply. These are the "I just deployed staging, add
# the URL" / "I added a new script, remember it" / "here's the admin URL"
# workflows.
# ---------------------------------------------------------------------------

async def handle_add_environment(args, ctx: MCPContext) -> str:
    """Add a ProjectEnvironment row (local / staging / prod / …).

    Idempotent: if an environment with the same `kind` already exists we
    UPDATE its URL + env_template_path instead of inserting a duplicate —
    typical use case is Claude re-deploying and the URL shifting.
    """
    from sqlalchemy import select

    from app.core.ulid import new_ulid
    from app.models.project import ProjectEnvironment

    project = await _resolve_project(args, ctx)
    kind = (getattr(args, "kind", "") or "").strip().lower()
    url = (getattr(args, "url", "") or "").strip()
    if not kind or not url:
        raise RuntimeError("kind and url are required")
    env_template_path = (getattr(args, "env_template_path", "") or None)
    db_alias = (getattr(args, "db_alias", "") or None)

    existing = (await ctx.db.execute(
        select(ProjectEnvironment).where(
            ProjectEnvironment.project_id == project.id,
            ProjectEnvironment.kind == kind,
        )
    )).scalar_one_or_none()
    if existing:
        existing.url = url[:2000]
        if env_template_path is not None:
            existing.env_template_path = env_template_path
        if db_alias is not None:
            existing.db_alias = db_alias
        action = "updated"
        env_id = existing.id
    else:
        row = ProjectEnvironment(
            id=new_ulid(),
            project_id=project.id,
            kind=kind[:20],
            url=url[:2000],
            env_template_path=env_template_path,
            db_alias=db_alias,
        )
        ctx.db.add(row)
        action = "created"
        env_id = row.id

    return json.dumps({
        "id": env_id, "project_slug": project.slug, "kind": kind, "url": url, "action": action,
    })


async def handle_add_link(args, ctx: MCPContext) -> str:
    """Add a ProjectLink (docs, api, metrics, admin, live, …).

    Dedups by URL — if a link with the same URL already exists on the
    project we just update its label/kind. This lets Claude re-announce
    'the docs are at X' without producing duplicate rows.
    """
    from sqlalchemy import select

    from app.core.ulid import new_ulid
    from app.models import ProjectLink

    project = await _resolve_project(args, ctx)
    url = (getattr(args, "url", "") or "").strip()
    label = (getattr(args, "label", "") or "").strip()
    kind = (getattr(args, "kind", "") or "other").strip().lower()
    if not url or not label:
        raise RuntimeError("url and label are required")

    existing = (await ctx.db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id == project.id,
            ProjectLink.url == url,
        )
    )).scalar_one_or_none()
    if existing:
        existing.label = label[:200]
        existing.kind = kind[:50]
        action = "updated"
        link_id = existing.id
    else:
        row = ProjectLink(
            id=new_ulid(),
            project_id=project.id,
            kind=kind[:50],
            label=label[:200],
            url=url[:2000],
        )
        ctx.db.add(row)
        action = "created"
        link_id = row.id

    return json.dumps({
        "id": link_id, "project_slug": project.slug, "kind": kind, "label": label, "url": url,
        "action": action,
    })


async def handle_add_command(args, ctx: MCPContext) -> str:
    """Add a ProjectCommand (runnable shell/browser command).

    Dedups by `label` (case-insensitive). If a command with the same label
    already exists we update its `command` text so re-runs ("the dev
    command changed to pnpm turbo") don't spawn duplicates.
    """
    from sqlalchemy import func, select

    from app.core.ulid import new_ulid
    from app.models.project import ProjectCommand

    project = await _resolve_project(args, ctx)
    label = (getattr(args, "label", "") or "").strip()
    command = (getattr(args, "command", "") or "").strip()
    run_in = (getattr(args, "run_in", None) or "terminal")
    if run_in not in {"terminal", "browser"}:
        run_in = "terminal"
    confirm_required = 1 if getattr(args, "confirm_required", False) else 0
    if not label or not command:
        raise RuntimeError("label and command are required")

    existing = (await ctx.db.execute(
        select(ProjectCommand).where(
            ProjectCommand.project_id == project.id,
            func.lower(ProjectCommand.label) == label.lower(),
        )
    )).scalar_one_or_none()
    if existing:
        existing.command = command[:4000]
        existing.run_in = run_in
        existing.confirm_required = confirm_required
        action = "updated"
        cmd_id = existing.id
    else:
        row = ProjectCommand(
            id=new_ulid(),
            project_id=project.id,
            label=label[:200],
            command=command[:4000],
            run_in=run_in,
            confirm_required=confirm_required,
        )
        ctx.db.add(row)
        action = "created"
        cmd_id = row.id

    return json.dumps({
        "id": cmd_id, "project_slug": project.slug, "label": label, "action": action,
    })
