"""Per-project screenshot routes — preview, list, refresh, file serve."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import ProjectContext, require_project
from app.models import ProjectScreenshot
from app.schemas.screenshot import ScreenshotOut, ScreenshotRefreshOut
from app.services import screenshot_svc

router = APIRouter(prefix="/api/v1/projects/{slug}/screenshots", tags=["screenshots"])
preview_router = APIRouter(prefix="/api/v1/projects/{slug}", tags=["screenshots"])

DbDep = Annotated[AsyncSession, Depends(get_db)]
CtxDep = Annotated[ProjectContext, Depends(require_project)]


def _row_to_out(row: ProjectScreenshot, slug: str) -> ScreenshotOut:
    return ScreenshotOut(
        id=row.id,
        project_id=row.project_id,
        kind=row.kind,
        mime_type=row.mime_type,
        width=row.width,
        height=row.height,
        captured_at=row.captured_at,
        ship_id=row.ship_id,
        caption=row.caption,
        source_url=row.source_url,
        url=f"/api/v1/projects/{slug}/screenshots/{row.id}/file",
    )


@router.get("", response_model=list[ScreenshotOut])
async def list_(ctx: CtxDep, db: DbDep) -> list[ScreenshotOut]:
    rows = await screenshot_svc.list_screenshots(db, project=ctx.project)
    return [_row_to_out(r, ctx.project.slug) for r in rows]


@router.post(
    "/refresh",
    response_model=ScreenshotRefreshOut,
    status_code=status.HTTP_201_CREATED,
)
async def refresh(ctx: CtxDep, db: DbDep) -> ScreenshotRefreshOut:
    """Manually trigger a fresh capture. Blocks until chromium returns (~2-8s)."""
    row = await screenshot_svc.capture_project(db, project=ctx.project, kind="manual")
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="project has no landing / prod URL to screenshot",
        )
    await db.commit()
    return ScreenshotRefreshOut(screenshot=_row_to_out(row, ctx.project.slug))


@router.get("/{screenshot_id}/file")
async def get_file(
    screenshot_id: Annotated[str, Path(min_length=26, max_length=26)],
    ctx: CtxDep,
    db: DbDep,
) -> FileResponse:
    row = (await db.execute(
        select(ProjectScreenshot).where(
            ProjectScreenshot.id == screenshot_id,
            ProjectScreenshot.project_id == ctx.project.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="screenshot not found")
    path = screenshot_svc.storage_path(row.storage_key)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file missing on disk")
    # Long cache — the storage key is ULID-based so unique per capture.
    return FileResponse(
        path,
        media_type=row.mime_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@preview_router.get("/preview")
async def preview(ctx: CtxDep, db: DbDep) -> Response:
    """Redirect to the latest screenshot's file URL, or 204 if none yet."""
    row = await screenshot_svc.latest_screenshot(db, project=ctx.project)
    if row is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    url = f"/api/v1/projects/{ctx.project.slug}/screenshots/{row.id}/file"
    # Short-cache the redirect itself so the frontend re-checks after an hour,
    # but each underlying file is immutable and long-cached.
    return Response(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": url, "Cache-Control": "public, max-age=300"},
    )
