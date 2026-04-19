"""Launch (PH/HN/X/etc.) schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

LaunchPlatform = Literal["ph", "hn", "x", "reddit", "newsletter", "other"]


class LaunchIn(BaseModel):
    platform: LaunchPlatform
    launched_at: datetime
    url: str | None = Field(default=None, max_length=2_000)
    metrics: dict[str, Any] = Field(default_factory=dict)


class LaunchUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=2_000)
    metrics: dict[str, Any] | None = None


class LaunchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    platform: str
    launched_at: datetime
    url: str | None = None
    metrics: dict[str, Any] = {}
