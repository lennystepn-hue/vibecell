"""Session (coding-block) CRUD."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.core.ulid import new_ulid
from app.models import Project, Session


async def list_sessions(
    db: AsyncSession,
    *,
    project: Project,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[Session], str | None]:
    stmt = select(Session).where(Session.project_id == project.id)
    if cursor is not None:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as e:
            raise ValidationError(detail=f"invalid cursor: {e}") from e
        stmt = stmt.where(Session.started_at < cursor_dt)
    stmt = stmt.order_by(Session.started_at.desc()).limit(limit + 1)
    rows = list((await db.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].started_at.isoformat() if has_more and items else None
    return items, next_cursor


async def get_session(db: AsyncSession, *, project: Project, session_id: str) -> Session:
    row = (await db.execute(
        select(Session).where(
            Session.project_id == project.id, Session.id == session_id
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("session", session_id)
    return row


async def create_session(
    db: AsyncSession,
    *,
    project: Project,
    started_at: datetime,
    ended_at: datetime | None,
    summary: str | None,
    files_touched: list[Any],
    commits: list[Any],
    next_step: str | None,
    source: str,
) -> Session:
    row = Session(
        id=new_ulid(),
        project_id=project.id,
        started_at=started_at,
        ended_at=ended_at,
        summary=summary,
        files_touched=files_touched,
        commits=commits,
        next_step=next_step,
        source=source,
    )
    db.add(row)
    await db.flush()

    from app.services import events as events_svc
    await events_svc.publish(project.id, "session.created", {"session_id": row.id})
    return row


async def update_session(
    db: AsyncSession,
    *,
    project: Project,
    session_id: str,
    **fields: Any,
) -> Session:
    row = await get_session(db, project=project, session_id=session_id)
    for k, v in fields.items():
        if v is not None:
            setattr(row, k, v)
    await db.flush()
    return row


async def delete_session(
    db: AsyncSession, *, project: Project, session_id: str
) -> None:
    row = await get_session(db, project=project, session_id=session_id)
    await db.delete(row)
    await db.flush()
