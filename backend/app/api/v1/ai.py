"""AI features — BYOK-powered server-side endpoints.

Each endpoint resolves the project's Anthropic key (project secret → platform
fallback) and calls the AI service. Returns generated content plus a `meta`
object with token counts + key-source for UI display.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import AuthContext, ProjectContext, require_auth, require_project
from app.models import Decision, Project, ProjectContext as PCtx, Session, Ship
from app.services import ai as ai_svc
from app.services import todo_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/ai", tags=["ai"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]
AuthDep = Annotated[AuthContext, Depends(require_auth)]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AIMeta(BaseModel):
    model: str | None = None
    key_source: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class PlanTodosIn(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000)
    commit: bool = Field(default=True, description="If true, persist the todos as a batch; if false, preview only.")


class PlanTodosOut(BaseModel):
    batch: str
    titles: list[str]
    todo_ids: list[str]
    meta: AIMeta


class LaunchCopyIn(BaseModel):
    ship_id: str | None = None
    platforms: list[str] = Field(
        default_factory=lambda: ["twitter_x", "linkedin", "indiehackers", "product_hunt"],
    )


class LaunchPost(BaseModel):
    platform: str
    text: str


class LaunchCopyOut(BaseModel):
    posts: list[LaunchPost]
    meta: AIMeta


class RetroOut(BaseModel):
    markdown: str
    meta: AIMeta


class BriefOut(BaseModel):
    brief: str
    meta: AIMeta


class AIStatusOut(BaseModel):
    """Does this project have a usable AI key? Surfaced in the settings UI."""
    available: bool
    source: str | None  # "project-secret" | "platform-fallback" | None
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _project_context_blob(db: AsyncSession, project: Project) -> str:
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


async def _last_session_summary(db: AsyncSession, project: Project) -> str:
    row = (await db.execute(
        select(Session)
        .where(Session.project_id == project.id)
        .order_by(Session.started_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if not row:
        return "(no previous sessions logged yet)"
    when = row.started_at.isoformat() if row.started_at else "?"
    return f"Last session at {when}: {row.summary or '(empty)'}\nNext step: {row.next_step or '(none)'}"


async def _recent_decisions(db: AsyncSession, project: Project, n: int = 3) -> str:
    rows = (await db.execute(
        select(Decision)
        .where(Decision.project_id == project.id)
        .order_by(Decision.created_at.desc())
        .limit(n)
    )).scalars().all()
    if not rows:
        return "(no decisions logged)"
    lines = []
    for d in rows:
        lines.append(f"- {d.title}: {d.decision[:140]}")
    return "\n".join(lines)


async def _events_summary_since_ship(db: AsyncSession, project: Project) -> str:
    """Events since the most recent ship — used for retros."""
    latest_ship = (await db.execute(
        select(Ship).where(Ship.project_id == project.id)
        .order_by(Ship.shipped_at.desc()).limit(1)
    )).scalar_one_or_none()
    cutoff = latest_ship.shipped_at if latest_ship else None

    session_stmt = select(Session).where(Session.project_id == project.id)
    decision_stmt = select(Decision).where(Decision.project_id == project.id)
    if cutoff is not None:
        session_stmt = session_stmt.where(Session.started_at > cutoff)
        decision_stmt = decision_stmt.where(Decision.created_at > cutoff)

    sessions = (await db.execute(
        session_stmt.order_by(Session.started_at.asc())
    )).scalars().all()
    decisions = (await db.execute(
        decision_stmt.order_by(Decision.created_at.asc())
    )).scalars().all()

    lines: list[str] = []
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

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=AIStatusOut)
async def status_(ctx: CtxDep, auth: AuthDep, db: DbDep) -> AIStatusOut:
    """Tell the UI whether this project has a usable AI key and where it comes from."""
    try:
        _key, source = await ai_svc._resolve_anthropic_key(  # noqa: SLF001
            db, ctx.project, workspace_id=auth.active_workspace_id,
        )
    except ai_svc.AIConfigError as exc:
        return AIStatusOut(available=False, source=None, message=str(exc))
    return AIStatusOut(
        available=True,
        source=source,
        message=(
            "Using your own ANTHROPIC_API_KEY stored on this project."
            if source == "project-secret"
            else "Using the platform-provided fallback key. "
                 "For your own billing, store one via vibecell.secret_set."
        ),
    )


@router.post("/plan_todos", response_model=PlanTodosOut)
async def plan_todos(
    body: PlanTodosIn, ctx: CtxDep, auth: AuthDep, db: DbDep,
) -> PlanTodosOut:
    """Break a free-text goal into a batch of todos using the user's AI key.

    Side effect: if commit=true (default) the batch is persisted and todo.*
    events fire so the dashboard updates live.
    """
    context = await _project_context_blob(db, ctx.project)
    try:
        batch, titles, meta = await ai_svc.plan_todos(
            db,
            project=ctx.project,
            workspace_id=auth.active_workspace_id,
            goal=body.goal,
            context_brief=context,
        )
    except ai_svc.AIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc

    todo_ids: list[str] = []
    if body.commit and titles:
        rows = await todo_svc.create_batch(
            db,
            project=ctx.project,
            batch=batch,
            items=[{"title": t} for t in titles],
        )
        todo_ids = [r.id for r in rows]
        await db.commit()

    return PlanTodosOut(
        batch=batch, titles=titles, todo_ids=todo_ids, meta=AIMeta(**meta),
    )


@router.post("/launch_copy", response_model=LaunchCopyOut)
async def launch_copy(
    body: LaunchCopyIn, ctx: CtxDep, auth: AuthDep, db: DbDep,
) -> LaunchCopyOut:
    """Generate platform-specific launch posts for a ship event."""
    ship = None
    if body.ship_id:
        ship = (await db.execute(
            select(Ship).where(
                Ship.id == body.ship_id, Ship.project_id == ctx.project.id,
            )
        )).scalar_one_or_none()
    if ship is None:
        # Latest ship
        ship = (await db.execute(
            select(Ship).where(Ship.project_id == ctx.project.id)
            .order_by(Ship.shipped_at.desc()).limit(1)
        )).scalar_one_or_none()
    if ship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ship events yet — run vibecell.ship first.",
        )

    ctx_blob = await _project_context_blob(db, ctx.project)
    ship_blob = (
        f"{ctx_blob}\n"
        f"Ship version: {ship.version or '?'}\n"
        f"Ship summary: {ship.summary or '(empty)'}\n"
        f"Changelog (if any):\n{ship.changelog_md or '(empty)'}\n"
    )

    try:
        posts, meta = await ai_svc.launch_copy(
            db,
            project=ctx.project,
            workspace_id=auth.active_workspace_id,
            ship_context=ship_blob,
            platforms=body.platforms,
        )
    except ai_svc.AIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc

    return LaunchCopyOut(
        posts=[LaunchPost(**p) for p in posts], meta=AIMeta(**meta),
    )


@router.post("/retro", response_model=RetroOut)
async def retro(ctx: CtxDep, auth: AuthDep, db: DbDep) -> RetroOut:
    """Generate a markdown retro covering everything since the last ship."""
    events = await _events_summary_since_ship(db, ctx.project)
    try:
        md, meta = await ai_svc.retro(
            db,
            project=ctx.project,
            workspace_id=auth.active_workspace_id,
            events_summary=events,
        )
    except ai_svc.AIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    return RetroOut(markdown=md, meta=AIMeta(**meta))


@router.post("/resume_brief", response_model=BriefOut)
async def resume_brief(ctx: CtxDep, auth: AuthDep, db: DbDep) -> BriefOut:
    """Generate the funny "where the fuck was I" morning brief."""
    context = await _project_context_blob(db, ctx.project)
    last = await _last_session_summary(db, ctx.project)
    decisions = await _recent_decisions(db, ctx.project, n=3)
    blob = f"{context}\nLAST SESSION:\n{last}\n\nRECENT DECISIONS:\n{decisions}\n"
    try:
        text, meta = await ai_svc.resume_brief(
            db,
            project=ctx.project,
            workspace_id=auth.active_workspace_id,
            context_blob=blob,
        )
    except ai_svc.AIConfigError as exc:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)) from exc
    return BriefOut(brief=text, meta=AIMeta(**meta))
