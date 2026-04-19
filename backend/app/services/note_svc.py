"""Project notes (singleton markdown scratchpad)."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note, Project


async def get_note(db: AsyncSession, *, project: Project) -> Note | None:
    return (await db.execute(
        select(Note).where(Note.project_id == project.id)
    )).scalar_one_or_none()


async def upsert_note(
    db: AsyncSession, *, project: Project, markdown: str
) -> Note:
    row = await get_note(db, project=project)
    if row is None:
        row = Note(project_id=project.id, markdown=markdown)
        db.add(row)
    else:
        row.markdown = markdown
        row.updated_at = datetime.now(UTC)
    await db.flush()
    return row
