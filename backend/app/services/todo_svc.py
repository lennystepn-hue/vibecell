"""Project-todo CRUD + batch ops + smart 'match what I just did' matching.

Every write publishes a live-event so the dashboard updates without a
page refresh. See app/services/events.py.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Project, ProjectTodo
from app.services import events as events_svc

ALLOWED_STATUSES = {"open", "in_progress", "done", "cancelled"}
ALLOWED_COMPLETED_BY = {"user", "claude"}


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------

async def list_todos(
    db: AsyncSession,
    *,
    project: Project,
    include_done: bool = True,
) -> list[ProjectTodo]:
    stmt = select(ProjectTodo).where(ProjectTodo.project_id == project.id)
    if not include_done:
        stmt = stmt.where(ProjectTodo.status.in_(["open", "in_progress"]))
    stmt = stmt.order_by(
        # Open items at the top in position order, then in_progress, then done
        # at the bottom in reverse-completion order so freshly-ticked work
        # stays visible momentarily.
        (ProjectTodo.status == "done").asc(),
        ProjectTodo.batch.nulls_last(),
        ProjectTodo.position.asc(),
        ProjectTodo.created_at.asc(),
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_todo(
    db: AsyncSession, *, project: Project, todo_id: str,
) -> ProjectTodo:
    row = (await db.execute(
        select(ProjectTodo).where(
            ProjectTodo.id == todo_id,
            ProjectTodo.project_id == project.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("todo", todo_id)
    return row


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

async def _next_position(
    db: AsyncSession, *, project_id: str, batch: str | None,
) -> int:
    """Assign the next position within a batch (or ungrouped bucket)."""
    stmt = select(func.coalesce(func.max(ProjectTodo.position), -1) + 1).where(
        ProjectTodo.project_id == project_id,
    )
    if batch is None:
        stmt = stmt.where(ProjectTodo.batch.is_(None))
    else:
        stmt = stmt.where(ProjectTodo.batch == batch)
    return int((await db.execute(stmt)).scalar() or 0)


async def create_todo(
    db: AsyncSession,
    *,
    project: Project,
    title: str,
    body: str | None = None,
    batch: str | None = None,
    position: int | None = None,
) -> ProjectTodo:
    pos = position if position is not None else await _next_position(
        db, project_id=project.id, batch=batch,
    )
    row = ProjectTodo(
        id=new_ulid(),
        project_id=project.id,
        title=title,
        body=body,
        batch=batch,
        position=pos,
    )
    db.add(row)
    await db.flush()
    await events_svc.publish(
        project.id, "todo.created", {"todo_id": row.id, "batch": batch},
    )
    return row


async def create_batch(
    db: AsyncSession,
    *,
    project: Project,
    batch: str,
    items: list[dict[str, Any]],
) -> list[ProjectTodo]:
    """Create several todos under the same batch label in one go."""
    rows: list[ProjectTodo] = []
    base_pos = await _next_position(db, project_id=project.id, batch=batch)
    for i, item in enumerate(items):
        rows.append(ProjectTodo(
            id=new_ulid(),
            project_id=project.id,
            title=item["title"],
            body=item.get("body"),
            batch=batch,
            position=base_pos + i,
        ))
    db.add_all(rows)
    await db.flush()
    await events_svc.publish(
        project.id, "todo.batch_created",
        {"batch": batch, "count": len(rows)},
    )
    return rows


async def update_todo(
    db: AsyncSession,
    *,
    project: Project,
    todo_id: str,
    **fields: Any,
) -> ProjectTodo:
    row = await get_todo(db, project=project, todo_id=todo_id)
    status = fields.pop("status", None)
    if status is not None:
        if status not in ALLOWED_STATUSES:
            raise ValidationError(detail=f"invalid status {status!r}")
        row.status = status
        now = datetime.now(UTC)
        if status == "in_progress" and row.started_at is None:
            row.started_at = now
        if status in {"done", "cancelled"}:
            row.completed_at = now
    for k, v in fields.items():
        if v is not None and hasattr(row, k):
            setattr(row, k, v)
    await db.flush()
    await events_svc.publish(project.id, "todo.updated", {"todo_id": row.id})
    return row


async def start_todo(
    db: AsyncSession, *, project: Project, todo_id: str,
) -> ProjectTodo:
    """Mark a todo as in_progress — used by Claude right before working on it."""
    row = await get_todo(db, project=project, todo_id=todo_id)
    row.status = "in_progress"
    row.started_at = datetime.now(UTC)
    await db.flush()
    await events_svc.publish(project.id, "todo.started", {"todo_id": row.id})
    return row


async def complete_todo(
    db: AsyncSession,
    *,
    project: Project,
    todo_id: str,
    completed_by: str = "user",
    completion_note: str | None = None,
) -> ProjectTodo:
    if completed_by not in ALLOWED_COMPLETED_BY:
        raise ValidationError(detail=f"completed_by must be one of {sorted(ALLOWED_COMPLETED_BY)}")
    row = await get_todo(db, project=project, todo_id=todo_id)
    row.status = "done"
    row.completed_at = datetime.now(UTC)
    row.completed_by = completed_by
    row.completion_note = completion_note
    await db.flush()
    await events_svc.publish(
        project.id, "todo.completed",
        {"todo_id": row.id, "completed_by": completed_by},
    )
    return row


async def delete_todo(
    db: AsyncSession, *, project: Project, todo_id: str,
) -> None:
    row = await get_todo(db, project=project, todo_id=todo_id)
    await db.delete(row)
    await db.flush()
    await events_svc.publish(project.id, "todo.deleted", {"todo_id": todo_id})


# ---------------------------------------------------------------------------
# Smart matching — "I just did X, tick whichever open todo matches"
# ---------------------------------------------------------------------------

def _score_match(query: str, row: ProjectTodo) -> int:
    """Crude keyword score: count matching words between query and title+body.

    Good enough for a first pass; a future iteration can swap in pgvector or
    tsvector FTS once we have enough todos to justify the dependency.
    """
    if not query:
        return 0
    q_tokens = {t.lower() for t in query.split() if len(t) >= 3}
    if not q_tokens:
        return 0
    hay = (row.title or "") + " " + (row.body or "")
    hay_tokens = {t.lower() for t in hay.split() if len(t) >= 3}
    return len(q_tokens & hay_tokens)


async def match_open_todo(
    db: AsyncSession, *, project: Project, description: str,
) -> ProjectTodo | None:
    """Return the best-matching open todo for the given free-text description.

    Used by the MCP tool `vibecell.todo_match` so Claude can tell us "I just
    finished wiring X" and we auto-flag the correct entry.
    """
    open_rows = await list_todos(db, project=project, include_done=False)
    if not open_rows:
        return None
    scored = sorted(
        ((_score_match(description, r), r) for r in open_rows),
        key=lambda x: x[0],
        reverse=True,
    )
    best_score, best_row = scored[0]
    return best_row if best_score >= 1 else None
