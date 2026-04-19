"""Decision (ADR-lite) CRUD."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.core.ulid import new_ulid
from app.models import Decision, Project


async def list_decisions(db: AsyncSession, *, project: Project) -> list[Decision]:
    return list((await db.execute(
        select(Decision)
        .where(Decision.project_id == project.id)
        .order_by(Decision.created_at.desc())
    )).scalars())


async def get_decision(
    db: AsyncSession, *, project: Project, decision_id: str
) -> Decision:
    row = (await db.execute(
        select(Decision).where(
            Decision.project_id == project.id, Decision.id == decision_id
        )
    )).scalar_one_or_none()
    if row is None:
        raise NotFoundError("decision", decision_id)
    return row


async def create_decision(
    db: AsyncSession,
    *,
    project: Project,
    title: str,
    context: str | None,
    decision: str,
    consequences: str | None,
    reconsider_if: str | None,
) -> Decision:
    row = Decision(
        id=new_ulid(),
        project_id=project.id,
        title=title,
        context=context,
        decision=decision,
        consequences=consequences,
        reconsider_if=reconsider_if,
    )
    db.add(row)
    await db.flush()
    return row


async def delete_decision(
    db: AsyncSession, *, project: Project, decision_id: str
) -> None:
    row = await get_decision(db, project=project, decision_id=decision_id)
    await db.delete(row)
    await db.flush()
