"""Portfolio Intelligence service — cross-project snapshot generation.

Spec 5B — Portfolio-Intel.

Status: STUB with real query skeleton.
generate_snapshot() composes activity counts from existing tables and returns
a structured dict. The result is not yet persisted to portfolio_snapshot.
Full implementation deferred to Spec 5B.1.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Activity counts older than this are ignored in stagnation detection
_STAGNATION_DAYS = 30


async def generate_snapshot(workspace_id: str) -> dict[str, Any]:
    """Generate a portfolio snapshot for a workspace.

    Queries:
    - Project list + status
    - Activity events (ships, sessions, decisions, notes) per project/week
    - Stagnation: projects with no activity in >30 days

    STUB: queries are wired, but results are returned in-memory and NOT
    persisted to portfolio_snapshot. Full persistence deferred to 5B.1.

    Returns a dict matching the snapshot shape defined in the design doc.
    """
    from sqlalchemy import func, select, text
    from app.core.db import session_scope
    from app.models.project import Project
    from app.models.ship_loop import Ship, Session, Decision, Note  # noqa: F401

    generated_at = datetime.now(timezone.utc)
    stagnation_cutoff = generated_at - timedelta(days=_STAGNATION_DAYS)

    async with session_scope() as db:
        # --- Project list ---
        projects = (await db.execute(
            select(Project.id, Project.slug, Project.name, Project.status)
            .where(Project.workspace_id == workspace_id)
            .where(Project.archived_at.is_(None))
            .order_by(Project.position)
        )).all()

        if not projects:
            logger.debug("portfolio_intel: workspace=%s has no active projects", workspace_id)
            return _empty_snapshot(workspace_id, generated_at)

        project_ids = [p[0] for p in projects]
        project_map = {p[0]: {"slug": p[1], "name": p[2], "status": p[3]} for p in projects}

        # --- Last activity per project ---
        # We look at the max timestamp across ships + sessions + decisions + notes
        # This is a simplified approach; a full impl would use a UNION query.
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

        # Note has project_id as PK + updated_at (no separate id column)
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
                    days = (
                        (generated_at - last_ts).days if last_ts else 9999
                    )
                    stagnant.append({
                        "project_id": pid,
                        "slug": proj["slug"],
                        "name": proj["name"],
                        "days_since_activity": days,
                        "last_activity_at": last_ts.isoformat() if last_ts else None,
                    })

        # --- Activity by week (rolling 12 weeks, ships only for now) ---
        # Full impl would union ships + sessions + decisions + notes
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
        "recommendations": [],  # Phase 5B.3
        "dependency_alerts": [],  # Phase 5B.2
    }

    logger.info(
        "portfolio_intel.generate_snapshot: workspace=%s projects=%d stagnant=%d [STUB — not persisted]",
        workspace_id,
        len(projects),
        len(stagnant),
    )
    return snapshot


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
