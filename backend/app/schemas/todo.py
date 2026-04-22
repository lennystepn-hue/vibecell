"""Public shapes for project todos."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TodoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    batch: str | None
    title: str
    body: str | None
    status: str
    position: int
    completed_by: str | None
    completion_note: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class TodoIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=2000)
    body: str | None = Field(default=None, max_length=10_000)
    batch: str | None = Field(default=None, max_length=120)
    position: int | None = None


class TodoBatchIn(BaseModel):
    """Create many todos at once under a single batch label."""

    batch: str = Field(..., min_length=1, max_length=120)
    items: list[TodoIn] = Field(..., min_length=1, max_length=50)


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=2000)
    body: str | None = None
    batch: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, pattern="^(open|in_progress|done|cancelled)$")
    position: int | None = None


class TodoCompleteIn(BaseModel):
    """Payload for claude-driven or user-driven completion."""

    completion_note: str | None = Field(default=None, max_length=2000)
    completed_by: str = Field(default="user", pattern="^(user|claude)$")
