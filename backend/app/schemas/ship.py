"""Ship (release event) schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ShipIn(BaseModel):
    shipped_at: datetime | None = None
    version: str | None = Field(default=None, max_length=50)
    summary: str | None = Field(default=None, max_length=2_000)
    changelog_md: str | None = Field(default=None, max_length=50_000)


class ShipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    shipped_at: datetime
    version: str | None = None
    summary: str | None = None
    changelog_md: str | None = None
