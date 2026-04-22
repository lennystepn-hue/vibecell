"""Public shapes for project screenshots."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ScreenshotOut(BaseModel):
    """One screenshot row. `url` is the download URL relative to the API host."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: str
    mime_type: str
    width: int | None
    height: int | None
    captured_at: datetime
    ship_id: str | None
    caption: str | None
    source_url: str | None
    url: str  # populated by the route: /api/v1/projects/{slug}/screenshots/{id}/file


class ScreenshotRefreshOut(BaseModel):
    """Returned by the POST /refresh endpoint — the just-captured screenshot."""

    screenshot: ScreenshotOut
