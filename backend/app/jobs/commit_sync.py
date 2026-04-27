"""GitHub commit → session-row sync cron.

Fires every 10 minutes. For each workspace with a GitHub integration,
walks every project that has a GitHub URL and pulls the recent commit
list via the GitHub REST API. Any commit SHA NOT already referenced by
an existing session row gets its own auto-session with source="github".

This is the safety net behind the SKILL.md commit-log rule. Even if Claude
skips a log (or the user isn't using Claude at all, just pushing from
the terminal), the dashboard still catches up within ~10 minutes.

Idempotency: match by exact SHA across every session's `commits` JSONB
array. Once a SHA is logged by EITHER the skill or this cron, we don't
duplicate it. First-time sync for a project is bounded to the last 7
days so we don't backfill years of history into fake "sessions".
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import session_scope
from app.core.ulid import new_ulid
from app.models import Project, ProjectLink, Session, Ship, Workspace
from app.services import integration as integ_svc

logger = logging.getLogger(__name__)

_GITHUB_COMMITS_URL = "https://api.github.com/repos/{owner}/{repo}/commits"
_GITHUB_TAGS_URL = "https://api.github.com/repos/{owner}/{repo}/tags"
_LOOKBACK_DAYS = 7
_VERSION_TAG = re.compile(r"^v?\d+\.\d+(\.\d+)?([-.][a-z0-9.-]+)?$", re.IGNORECASE)


def _parse_owner_repo(url: str) -> tuple[str, str] | None:
    """Pull (owner, repo) out of a GitHub HTTPS or SSH URL."""
    m = re.search(r"github\.com[:/]([^/]+)/([^/.\s]+)", url or "")
    if not m:
        return None
    return m.group(1), m.group(2)


async def _existing_shas_for_project(db: AsyncSession, project_id: str) -> set[str]:
    """Return every commit SHA ever referenced by a session on this project.

    Uses Postgres JSONB array containment by flattening to a set. Cheap for
    the volumes we expect (<1000 sessions/project).
    """
    rows = (await db.execute(
        select(Session.commits).where(Session.project_id == project_id)
    )).scalars().all()
    shas: set[str] = set()
    for commits in rows:
        if not isinstance(commits, list):
            continue
        for c in commits:
            if isinstance(c, dict):
                sha = c.get("sha")
                if isinstance(sha, str) and sha:
                    shas.add(sha[:40])
    return shas


async def _fetch_recent_commits(
    token: str,
    owner: str,
    repo: str,
    since_iso: str,
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    """Pull commits newer than `since_iso` from GitHub. Caps at 3 pages x 100."""
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20) as client:
        for page in range(1, max_pages + 1):
            try:
                r = await client.get(
                    _GITHUB_COMMITS_URL.format(owner=owner, repo=repo),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    params={"since": since_iso, "per_page": 100, "page": page},
                )
            except Exception:
                break
            if r.status_code != 200:
                break
            batch: list[dict[str, Any]] = r.json()
            if not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
    return out


async def _sync_project(db: AsyncSession, workspace_id: str, project: Project, token: str) -> int:
    """Sync commits for one project. Returns the number of sessions inserted."""
    # Resolve owner/repo from the first github-kind link
    gh_link = (await db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id == project.id,
            ProjectLink.kind == "github",
        ).limit(1)
    )).scalar_one_or_none()
    if gh_link is None:
        return 0
    pair = _parse_owner_repo(gh_link.url or "")
    if not pair:
        return 0
    owner, repo = pair

    # Cursor: the newest commit SHA we've already logged → fetch everything
    # since the project was imported, capped at 7 days for the first run.
    since = datetime.now(UTC) - timedelta(days=_LOOKBACK_DAYS)
    existing = await _existing_shas_for_project(db, project.id)
    # If we already have some commits logged, narrow the window to the last
    # of our stored commit dates (small win on rate limit, safe because the
    # existing-SHA set dedups regardless).
    if existing:
        latest_session_at = (await db.execute(
            select(func.max(Session.started_at)).where(
                Session.project_id == project.id
            )
        )).scalar_one_or_none()
        if latest_session_at is not None:
            # Back off a day to catch anything that came in out-of-order.
            narrowed = latest_session_at - timedelta(days=1)
            if narrowed > since:
                since = narrowed

    commits = await _fetch_recent_commits(
        token, owner, repo, since_iso=since.isoformat()
    )
    if not commits:
        return 0

    inserted = 0
    for c in commits:
        sha = c.get("sha")
        if not isinstance(sha, str) or not sha:
            continue
        if sha in existing:
            continue
        existing.add(sha)
        commit_obj = c.get("commit") or {}
        msg = (commit_obj.get("message") or "").strip()
        if not msg:
            continue
        # first line of the commit message = session summary
        first_line = msg.split("\n", 1)[0][:500]
        # Use the actual commit author date as the session's started_at so
        # older commits don't all cluster at "now".
        author = commit_obj.get("author") or {}
        ts_iso = author.get("date") or datetime.now(UTC).isoformat()
        try:
            started_at = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        except ValueError:
            started_at = datetime.now(UTC)

        db.add(Session(
            id=new_ulid(),
            project_id=project.id,
            started_at=started_at,
            ended_at=started_at,
            summary=first_line,
            files_touched=[],
            commits=[{"sha": sha[:40], "msg": first_line}],
            next_step=None,
            source="github",
        ))
        inserted += 1

        # Layer-1 auto-tick: try to match this commit's subject against an
        # open todo and tick it. Fuzzy match — only fires when score ≥ 1
        # (see todo_svc._score_match). Conservative on purpose: better to
        # miss a tick than to wrongly close an unrelated todo. Failure
        # here is silent — the commit→session sync is the contract, the
        # auto-tick is a bonus.
        try:
            await _auto_tick_from_commit(db, project, first_line, sha[:7])
        except Exception:
            logger.exception(
                "commit_sync: auto-tick crashed (non-fatal) project=%s sha=%s",
                project.slug, sha[:7],
            )

    if inserted:
        logger.info(
            "commit_sync: +%s session(s) for workspace=%s project=%s",
            inserted, workspace_id, project.slug,
        )
    # Also sync tags → ships for the same project while we have the token +
    # owner/repo resolved.
    inserted += await _sync_tags_for_project(db, workspace_id, project, token, owner, repo)
    return inserted


async def _auto_tick_from_commit(
    db: AsyncSession, project: Project, commit_subject: str, sha_short: str
) -> None:
    """If `commit_subject` looks like it completed an open todo, tick it.

    Reuses todo_svc.match_open_todo's scoring (≥ 1 threshold). The
    completion_note records both the commit subject and the SHA so the
    user can audit the auto-tick later in the dashboard.
    """
    from app.services import todo_svc

    matched = await todo_svc.match_open_todo(
        db, project=project, description=commit_subject
    )
    if matched is None:
        return
    note = f"auto-ticked from commit {sha_short}: {commit_subject}"
    await todo_svc.complete_todo(
        db,
        project=project,
        todo_id=matched.id,
        completed_by="commit_sync",
        completion_note=note[:2000],
    )
    logger.info(
        "commit_sync: auto-ticked todo %s for project=%s commit=%s",
        matched.id, project.slug, sha_short,
    )


async def _fetch_tags(token: str, owner: str, repo: str) -> list[dict[str, Any]]:
    """Pull the 100 most recent tags from GitHub."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                _GITHUB_TAGS_URL.format(owner=owner, repo=repo),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100},
            )
        if r.status_code == 200:
            return r.json()
    except Exception:
        return []
    return []


async def _sync_tags_for_project(
    db: AsyncSession, workspace_id: str, project: Project, token: str, owner: str, repo: str,
) -> int:
    """For each version-style tag (v1.2.3) not yet in `ships`, insert a Ship
    row with version=<tag>, summary derived from the pointed commit subject.
    """
    existing_versions = {
        v for v in (await db.execute(
            select(Ship.version).where(Ship.project_id == project.id)
        )).scalars().all()
        if v
    }
    tags = await _fetch_tags(token, owner, repo)
    inserted = 0
    for t in tags:
        name = (t.get("name") or "").strip()
        if not name or not _VERSION_TAG.match(name):
            continue
        # Dedup both the raw tag and a v-stripped variant, since users sometimes
        # ship as "1.2.3" once and "v1.2.3" another time.
        normalised = name.lstrip("vV")
        if name in existing_versions or normalised in existing_versions or f"v{normalised}" in existing_versions:
            continue
        sha = (t.get("commit") or {}).get("sha")
        # Use the tagged commit's author date so ship timestamps stay chronological.
        shipped_at = datetime.now(UTC)
        summary = None
        if sha:
            async with httpx.AsyncClient(timeout=10) as client:
                try:
                    cr = await client.get(
                        _GITHUB_COMMITS_URL.format(owner=owner, repo=repo) + f"/{sha}",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Accept": "application/vnd.github+json",
                        },
                    )
                    if cr.status_code == 200:
                        data = cr.json()
                        msg = ((data.get("commit") or {}).get("message") or "").strip()
                        if msg:
                            summary = msg.split("\n", 1)[0][:500]
                        date_iso = ((data.get("commit") or {}).get("author") or {}).get("date")
                        if date_iso:
                            try:
                                shipped_at = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                            except ValueError:
                                pass
                except Exception:
                    pass

        db.add(Ship(
            id=new_ulid(),
            project_id=project.id,
            shipped_at=shipped_at,
            version=name[:50],
            summary=summary or f"tagged {name}",
            changelog_md=None,
        ))
        existing_versions.add(name)
        inserted += 1

    if inserted:
        logger.info(
            "commit_sync: +%s ship(s) from git tags for ws=%s project=%s",
            inserted, workspace_id, project.slug,
        )
    return inserted


async def _run_sync_all() -> None:
    """Cron entry point: walk every workspace with a GitHub token + sync.

    Skips workspaces whose owner is in read-only mode (Stripe canceled /
    unpaid / no sub) — GitHub-API quota and our compute are paid features.
    """
    from app.models import Subscription
    from app.services.access_level import FULL_ACCESS_STATUSES
    try:
        async with session_scope() as db:
            workspaces = (
                await db.execute(
                    select(Workspace)
                    .join(Subscription, Subscription.user_id == Workspace.owner_id)
                    .where(Subscription.status.in_(list(FULL_ACCESS_STATUSES)))
                )
            ).scalars().all()
            total = 0
            for ws in workspaces:
                try:
                    token = await integ_svc.get_decrypted_token(
                        db, workspace_id=ws.id, kind="github",
                    )
                except Exception:
                    # Workspace has no GitHub integration → nothing to sync
                    continue
                if not token:
                    continue
                projects = (await db.execute(
                    select(Project).where(
                        Project.workspace_id == ws.id,
                        Project.archived_at.is_(None),
                    )
                )).scalars().all()
                for p in projects:
                    try:
                        total += await _sync_project(db, ws.id, p, token)
                    except Exception:
                        logger.exception(
                            "commit_sync: project sync crashed ws=%s slug=%s",
                            ws.id, p.slug,
                        )
            if total:
                await db.commit()
                logger.info("commit_sync: inserted %s total session(s)", total)
    except Exception:
        logger.exception("commit_sync: _run_sync_all crashed")


def schedule_commit_sync_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register the 2-min commit-sync cron — Layer 1 of the auto-logging
    safety net. Runs every 2 minutes so a forgotten vibecell_log_session
    call gets backstopped within 2 minutes (was 10 min). GitHub API cost
    is one `since=last-sync` request per workspace; cheap."""
    scheduler.add_job(
        _run_sync_all,
        "interval",
        minutes=2,
        id="commit_sync_all",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info("commit_sync: registered commit_sync_all every 2m")
