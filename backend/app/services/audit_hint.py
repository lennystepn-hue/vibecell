"""Layer-2 of the auto-logging safety net.

Every MCP tool response gets an `_audit_hint` block when the system
detects that Claude has been writing code (commits flowing in via the
GitHub-sync cron) but NOT logging the work via vibecell_log_session /
vibecell_todo_complete / vibecell_set_focus. The SKILL has a hard rule
that says "if `_audit_hint.suggested_action` is set, execute it before
your next user-facing response" — so this hint forces the discipline
mechanically rather than relying on Claude remembering the SKILL rules.

Why this works out-of-the-box: the user does nothing. The cron runs on
our server; the hint is computed from server state; it's injected
into every MCP tool response automatically. No CLI subcommand to
install, no settings.json hook to wire up.

What counts as drift:

  * **silent_commits** — count of recent `source='github'` Session rows
    (i.e. commits the cron found but Claude hadn't logged). > 0 means
    Claude has been committing without calling vibecell_log_session.

  * **matchable_todos** — open todos whose title fuzzy-matches a recent
    silent-commit subject. Suggests "you probably finished this todo".

  * **stale_focus_minutes** — minutes since `project_context.current_focus`
    was last touched. Only counts when there's RECENT activity (silent
    commits or fresh sessions); a quiet project doesn't get nagged.

Returns None when there's no drift — keep MCP responses clean in the
happy path.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, ProjectContext, Session

# Recency window — drift only counts within the last 30 min so old
# unlogged work doesn't keep nagging forever.
_RECENT_WINDOW = timedelta(minutes=30)
# Suggest a focus refresh if it hasn't been touched in this long AND
# there's been activity. Lower than the cron interval would be too noisy.
_STALE_FOCUS_AFTER = timedelta(minutes=20)


@dataclass(frozen=True, slots=True)
class AuditHint:
    silent_commits: int
    matchable_todos: list[dict[str, Any]]   # [{"id", "title", "match_subject"}]
    stale_focus_minutes: int | None         # None when fresh enough OR no activity
    suggested_action: str                    # canonical next move for Claude

    def to_dict(self) -> dict[str, Any]:
        return {
            "silent_commits": self.silent_commits,
            "matchable_todos": self.matchable_todos,
            "stale_focus_minutes": self.stale_focus_minutes,
            "suggested_action": self.suggested_action,
        }


async def compute_audit_hint(
    db: AsyncSession, *, project: Project | None
) -> AuditHint | None:
    """Compute the hint for the just-touched project. Returns None when
    nothing's wrong (clean state) so the MCP response stays minimal."""
    if project is None:
        return None

    now = datetime.now(UTC)
    cutoff = now - _RECENT_WINDOW

    # Recent github-sourced sessions = commits the cron found
    silent_rows = (
        await db.execute(
            select(Session)
            .where(Session.project_id == project.id)
            .where(Session.source == "github")
            .where(Session.started_at >= cutoff)
            .order_by(desc(Session.started_at))
            .limit(10)
        )
    ).scalars().all()

    silent_commits = len(silent_rows)

    # Recent non-github sessions = Claude actually logged something
    last_manual_log = (
        await db.execute(
            select(Session)
            .where(Session.project_id == project.id)
            .where(Session.source != "github")
            .order_by(desc(Session.started_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    last_manual_at = last_manual_log.started_at if last_manual_log else None

    # If the most recent github session is older than the most recent manual
    # log, Claude IS keeping up — no silent drift.
    if (
        last_manual_at and silent_rows
        and all(s.started_at <= last_manual_at for s in silent_rows)
    ):
        silent_commits = 0
        silent_rows = []

    # Try to match open todos against recent silent-commit subjects
    matchable: list[dict[str, Any]] = []
    if silent_rows:
        from app.services import todo_svc

        for sess in silent_rows[:5]:  # cap the matching budget
            subject = (sess.summary or "").strip()
            if not subject:
                continue
            best = await todo_svc.match_open_todo(
                db, project=project, description=subject
            )
            if best is not None and not any(m["id"] == best.id for m in matchable):
                matchable.append({
                    "id": best.id,
                    "title": best.title,
                    "match_subject": subject,
                })

    # Focus staleness — only complain when there's recent activity
    stale_focus_minutes: int | None = None
    if silent_commits > 0 or (last_manual_at and (now - last_manual_at) < _RECENT_WINDOW):
        ctx_row = (
            await db.execute(
                select(ProjectContext).where(ProjectContext.project_id == project.id)
            )
        ).scalar_one_or_none()
        if ctx_row is not None:
            # ProjectContext doesn't carry its own updated_at — approximate
            # via the row's last-touched timestamp if we have one. SQLAlchemy
            # adds an `updated_at` only when the model defines it; ProjectContext
            # may not, so we fall back to the last manual log time.
            ctx_updated = getattr(ctx_row, "updated_at", None) or last_manual_at
            if ctx_updated is not None:
                age = now - ctx_updated
                if age > _STALE_FOCUS_AFTER:
                    stale_focus_minutes = int(age.total_seconds() // 60)

    # Compose the canonical suggested_action — exactly one, ranked by impact
    suggested = ""
    if silent_commits > 0:
        n = silent_commits
        suggested = (
            f"call vibecell_log_session covering the {n} commit"
            f"{'s' if n > 1 else ''} you made since the last manual log "
            f"(use the most recent commit subject as the summary)"
        )
    elif matchable:
        first = matchable[0]
        suggested = (
            f"call vibecell_todo_match with auto_complete=true and "
            f"description='{first['match_subject'][:80]}' — looks like you "
            f"completed the open todo '{first['title'][:60]}'"
        )
    elif stale_focus_minutes is not None:
        suggested = (
            f"call vibecell_set_focus — current_focus has been stale for "
            f"{stale_focus_minutes} minutes and there's been activity since"
        )

    if not suggested:
        return None  # clean state — no hint emitted
    return AuditHint(
        silent_commits=silent_commits,
        matchable_todos=matchable,
        stale_focus_minutes=stale_focus_minutes,
        suggested_action=suggested,
    )
