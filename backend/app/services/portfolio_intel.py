"""Portfolio Intelligence service — cross-project snapshot generation + caching.

Spec 5B.1 — Portfolio-Intel. Full persistence implementation.

- generate_snapshot()   — compute fresh data, persist to portfolio_snapshot.
- get_or_generate()     — return cached snapshot (if <10 min old), else regenerate.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ulid import new_ulid
from app.models.signals import PortfolioSnapshot

logger = logging.getLogger(__name__)

_STAGNATION_DAYS = 30
_CACHE_TTL_MINUTES = 10


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------


async def generate_snapshot(workspace_id: str, db: AsyncSession) -> dict[str, Any]:
    """Compute a fresh portfolio snapshot and persist it to portfolio_snapshot."""
    from app.models.project import Project
    from app.models.ship_loop import Decision, Note, Session, Ship  # noqa: F401

    generated_at = datetime.now(timezone.utc)
    stagnation_cutoff = generated_at - timedelta(days=_STAGNATION_DAYS)

    # --- Project list ---
    projects = (await db.execute(
        select(Project.id, Project.slug, Project.name, Project.status)
        .where(Project.workspace_id == workspace_id)
        .where(Project.archived_at.is_(None))
        .order_by(Project.position)
    )).all()

    if not projects:
        logger.debug("portfolio_intel: workspace=%s has no active projects", workspace_id)
        snap = _empty_snapshot(workspace_id, generated_at)
        await _insert_snapshot(db, workspace_id, generated_at, snap)
        return snap

    project_ids = [p[0] for p in projects]
    project_map = {p[0]: {"slug": p[1], "name": p[2], "status": p[3]} for p in projects}

    # --- Last activity per project ---
    last_activity: dict[str, datetime | None] = {pid: None for pid in project_ids}

    for model, ts_col in [
        (Ship, Ship.shipped_at),
        (Session, Session.started_at),
        (Decision, Decision.created_at),
    ]:
        rows = (await db.execute(
            select(model.project_id, func.max(ts_col))
            .where(model.project_id.in_(project_ids))
            .group_by(model.project_id)
        )).all()
        for row_pid, max_ts in rows:
            if max_ts is not None:
                current = last_activity.get(row_pid)
                if current is None or max_ts > current:
                    last_activity[row_pid] = max_ts

    note_rows = (await db.execute(
        select(Note.project_id, Note.updated_at)
        .where(Note.project_id.in_(project_ids))
    )).all()
    for row_pid, note_ts in note_rows:
        if note_ts is not None:
            current = last_activity.get(row_pid)
            if current is None or note_ts > current:
                last_activity[row_pid] = note_ts

    # --- Stagnation ---
    stagnant = []
    for pid, last_ts in last_activity.items():
        if last_ts is None or last_ts < stagnation_cutoff:
            proj = project_map[pid]
            if proj["status"] not in ("archived", "shipped"):
                days = (generated_at - last_ts).days if last_ts else 9999
                stagnant.append({
                    "project_id": pid,
                    "slug": proj["slug"],
                    "name": proj["name"],
                    "days_since_activity": days,
                    "last_activity_at": last_ts.isoformat() if last_ts else None,
                })

    # --- Activity by week (rolling 12 weeks, ships) ---
    twelve_weeks_ago = generated_at - timedelta(weeks=12)
    ship_rows = (await db.execute(
        select(
            Ship.project_id,
            func.to_char(Ship.shipped_at, "IYYY-IW").label("iso_week"),
            func.count(Ship.id).label("event_count"),
        )
        .where(Ship.project_id.in_(project_ids))
        .where(Ship.shipped_at >= twelve_weeks_ago)
        .group_by(Ship.project_id, text("iso_week"))
    )).all()

    activity_by_week = [
        {
            "project_id": row[0],
            "week": f"{row[1][:4]}-W{row[1][5:]}",
            "event_count": row[2],
        }
        for row in ship_rows
    ]

    snapshot: dict[str, Any] = {
        "workspace_id": workspace_id,
        "generated_at": generated_at.isoformat(),
        "project_count": len(projects),
        "active_project_count": sum(
            1 for p in projects if p[3] not in ("archived", "shipped")
        ),
        "stagnant_projects": stagnant,
        "activity_by_week": activity_by_week,
        "recommendations": [],
        "dependency_alerts": [],
    }

    await _insert_snapshot(db, workspace_id, generated_at, snapshot)

    logger.info(
        "portfolio_intel.generate_snapshot: workspace=%s projects=%d stagnant=%d [persisted]",
        workspace_id,
        len(projects),
        len(stagnant),
    )
    return snapshot


async def _insert_snapshot(
    db: AsyncSession,
    workspace_id: str,
    generated_at: datetime,
    data: dict[str, Any],
) -> PortfolioSnapshot:
    row = PortfolioSnapshot(
        id=new_ulid(),
        workspace_id=workspace_id,
        generated_at=generated_at,
        data=data,
    )
    db.add(row)
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Cache logic
# ---------------------------------------------------------------------------


async def get_or_generate(workspace_id: str, db: AsyncSession, *, force: bool = False) -> dict[str, Any]:
    """Return a cached snapshot (<=10 min) or generate + persist a fresh one.

    Pass force=True to bypass the cache (e.g. ?refresh=true query param).
    """
    if not force:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=_CACHE_TTL_MINUTES)
        cached = (await db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.workspace_id == workspace_id)
            .where(PortfolioSnapshot.generated_at >= cutoff)
            .order_by(PortfolioSnapshot.generated_at.desc())
            .limit(1)
        )).scalar_one_or_none()

        if cached is not None:
            logger.debug(
                "portfolio_intel.get_or_generate: cache hit workspace=%s id=%s", workspace_id, cached.id
            )
            return {**cached.data, "_snapshot_id": cached.id, "_cache_hit": True}

    logger.debug("portfolio_intel.get_or_generate: generating fresh workspace=%s force=%s", workspace_id, force)
    data = await generate_snapshot(workspace_id, db)

    # Find the row we just inserted to attach its id
    row = (await db.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.workspace_id == workspace_id)
        .order_by(PortfolioSnapshot.generated_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    snap_id = row.id if row else None

    return {**data, "_snapshot_id": snap_id, "_cache_hit": False}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _empty_snapshot(workspace_id: str, generated_at: datetime) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "generated_at": generated_at.isoformat(),
        "project_count": 0,
        "active_project_count": 0,
        "stagnant_projects": [],
        "activity_by_week": [],
        "recommendations": [],
        "dependency_alerts": [],
    }
