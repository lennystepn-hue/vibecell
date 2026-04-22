"""Screenshot capture + storage orchestration.

Flow: resolve a project's target URL (healthcheck link or prod environment) →
launch headless chromium via playwright-async → grab viewport PNG → re-encode
as webp → write to a volume-mounted directory → persist a ProjectScreenshot row.

Designed to be called from three places:
- the scheduled refresh cron (kind="auto"),
- the ship_svc when a new ship is created (kind="ship", ship_id attached),
- a manual API endpoint (kind="manual").
"""
from __future__ import annotations

import asyncio
import io
import logging
from pathlib import Path
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ulid import new_ulid
from app.models import Project, ProjectEnvironment, ProjectLink, ProjectScreenshot

logger = logging.getLogger(__name__)

ScreenshotKind = Literal["auto", "ship", "manual", "moodboard"]
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
OUTPUT_WIDTH = 960  # downscale target — balances sharpness and file size
OUTPUT_QUALITY = 72  # webp quality
NAV_TIMEOUT_MS = 20_000
IDLE_TIMEOUT_MS = 4_000


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def storage_root() -> Path:
    """Directory where screenshot files live. Created on demand."""
    root = Path(get_settings().screenshots_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def storage_path(storage_key: str) -> Path:
    """Absolute filesystem path for a stored key — validates no path traversal."""
    root = storage_root().resolve()
    path = (root / storage_key).resolve()
    if not str(path).startswith(str(root)):
        raise ValueError(f"storage key escapes root: {storage_key!r}")
    return path


def _new_storage_key(project_id: str, kind: ScreenshotKind) -> str:
    """Generate a fresh, collision-free path under the project's directory."""
    return f"{project_id}/{new_ulid()}-{kind}.webp"


# ---------------------------------------------------------------------------
# URL resolution — which site should we screenshot?
# ---------------------------------------------------------------------------

async def resolve_capture_url(db: AsyncSession, project: Project) -> str | None:
    """Pick the best URL to screenshot for a project.

    Priority:
      1. ProjectLink with kind="landing"
      2. ProjectEnvironment with kind="prod"
      3. Any healthcheck link stripped of a trailing /healthz/status
      4. None — project has no public surface.
    """
    # (1) explicit landing link
    landing = (await db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id == project.id,
            ProjectLink.kind == "landing",
        ).limit(1)
    )).scalar_one_or_none()
    if landing and landing.url:
        return landing.url

    # (2) prod environment
    prod = (await db.execute(
        select(ProjectEnvironment).where(
            ProjectEnvironment.project_id == project.id,
            ProjectEnvironment.kind == "prod",
        ).limit(1)
    )).scalar_one_or_none()
    if prod and prod.url:
        return prod.url

    # (3) healthcheck link, trimmed to origin
    health = (await db.execute(
        select(ProjectLink).where(
            ProjectLink.project_id == project.id,
            ProjectLink.kind == "healthcheck",
        ).limit(1)
    )).scalar_one_or_none()
    if health and health.url:
        # crude trim: drop path after the 3rd slash if it looks like /healthz
        from urllib.parse import urlparse
        parsed = urlparse(health.url)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"

    return None


# ---------------------------------------------------------------------------
# Rendering — Playwright chromium
# ---------------------------------------------------------------------------

async def _render_webp(url: str) -> tuple[bytes, int, int]:
    """Launch chromium, navigate, capture viewport, return (webp_bytes, w, h).

    Raises if playwright is unavailable or navigation fails — callers should
    catch and convert to soft failures so a broken site never crashes a cron
    job or a user-facing API request.
    """
    from playwright.async_api import async_playwright  # deferred import

    try:
        from PIL import Image  # Pillow is already a common transitive dep
    except ImportError:  # pragma: no cover — surfaced during deploy
        raise RuntimeError("Pillow not installed — add to backend requirements") from None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",  # prevents OOM in constrained containers
                "--disable-gpu",
            ],
        )
        try:
            context = await browser.new_context(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=1,
                user_agent=(
                    "Mozilla/5.0 (compatible; Vibecell-Preview/1.0; "
                    "+https://vibecell.dev)"
                ),
            )
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
            # small extra delay for late-painting SPAs (Vue/React transitions)
            try:
                await page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
            except Exception:  # noqa: BLE001
                pass
            png_bytes = await page.screenshot(type="png", full_page=False)
        finally:
            await browser.close()

    # Re-encode PNG → WebP + downscale.
    img = Image.open(io.BytesIO(png_bytes))
    if img.width > OUTPUT_WIDTH:
        new_h = int(img.height * OUTPUT_WIDTH / img.width)
        img = img.resize((OUTPUT_WIDTH, new_h), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=OUTPUT_QUALITY, method=6)
    return out.getvalue(), img.width, img.height


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

async def capture_project(
    db: AsyncSession,
    *,
    project: Project,
    kind: ScreenshotKind = "auto",
    ship_id: str | None = None,
    override_url: str | None = None,
    caption: str | None = None,
) -> ProjectScreenshot | None:
    """Capture a screenshot for a project and persist it.

    Returns the new row, or None if the project has no capturable URL.
    Swallows and logs render failures — a broken site must not break the DB
    transaction of the caller (e.g. the ship handler).
    """
    url = override_url or await resolve_capture_url(db, project)
    if url is None:
        logger.info("skip screenshot: project %s has no public URL", project.slug)
        return None

    try:
        webp_bytes, w, h = await _render_webp(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("screenshot render failed for %s (%s): %s", project.slug, url, exc)
        return None

    key = _new_storage_key(project.id, kind)
    path = storage_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(webp_bytes)

    row = ProjectScreenshot(
        id=new_ulid(),
        project_id=project.id,
        kind=kind,
        storage_key=key,
        mime_type="image/webp",
        width=w,
        height=h,
        ship_id=ship_id,
        caption=caption,
        source_url=url,
    )
    db.add(row)
    await db.flush()

    # Fire live event so the dashboard updates without a reload.
    from app.services import events as events_svc
    await events_svc.publish(
        project.id,
        "screenshot.captured",
        {"screenshot_id": row.id, "kind": kind, "ship_id": ship_id},
    )

    return row


async def list_screenshots(
    db: AsyncSession, *, project: Project, limit: int = 30,
) -> list[ProjectScreenshot]:
    rows = (await db.execute(
        select(ProjectScreenshot)
        .where(ProjectScreenshot.project_id == project.id)
        .order_by(ProjectScreenshot.captured_at.desc())
        .limit(limit)
    )).scalars().all()
    return list(rows)


async def latest_screenshot(
    db: AsyncSession, *, project: Project,
) -> ProjectScreenshot | None:
    return (await db.execute(
        select(ProjectScreenshot)
        .where(ProjectScreenshot.project_id == project.id)
        .order_by(ProjectScreenshot.captured_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def refresh_all_auto(db: AsyncSession) -> int:
    """Scheduled job: capture "auto" kind for every project with a URL.

    Returns count of successfully captured screenshots. Errors per-project
    are logged and skipped.
    """
    projects = (await db.execute(
        select(Project).where(Project.archived_at.is_(None))
    )).scalars().all()
    captured = 0
    for p in projects:
        # Sequential (not parallel) to cap memory use on constrained VPSes —
        # chromium is heavy. Tune later if we outgrow this.
        try:
            row = await capture_project(db, project=p, kind="auto")
            if row is not None:
                captured += 1
            await db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning("refresh_all_auto: %s failed: %s", p.slug, exc)
            await db.rollback()
    return captured


# Convenience wrapper for fire-and-forget background captures (from API or
# ship handler) that don't want to block the response.
def schedule_background_capture(
    *,
    project_id: str,
    kind: ScreenshotKind,
    ship_id: str | None = None,
) -> None:
    """Schedule a capture in an asyncio background task.

    Used by the ship handler — it doesn't want to block the response on a
    5-second chromium launch. The background task opens its own DB session.
    """
    asyncio.create_task(_bg_capture(project_id, kind, ship_id))


async def _bg_capture(project_id: str, kind: ScreenshotKind, ship_id: str | None) -> None:
    from app.core.db import SessionLocal  # late import to avoid import cycle

    async with SessionLocal() as db:
        project = await db.get(Project, project_id)
        if project is None:
            return
        try:
            await capture_project(db, project=project, kind=kind, ship_id=ship_id)
            await db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("background screenshot capture failed")
            await db.rollback()
