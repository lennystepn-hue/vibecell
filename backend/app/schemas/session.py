"""Session (coding-block) schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SessionSource = Literal["skill", "manual", "cli"]


class SessionIn(BaseModel):
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=20_000)
    files_touched: list[Any] = Field(default_factory=list)
    commits: list[Any] = Field(default_factory=list)
    next_step: str | None = Field(default=None, max_length=2_000)
    source: SessionSource = "manual"


class SessionUpdate(BaseModel):
    ended_at: datetime | None = None
    summary: str | None = Field(default=None, max_length=20_000)
    next_step: str | None = Field(default=None, max_length=2_000)
    files_touched: list[Any] | None = None
    commits: list[Any] | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    started_at: datetime
    ended_at: datetime | None = None
    summary: str | None = None
    files_touched: list[Any] = []
    commits: list[Any] = []
    next_step: str | None = None
    source: str


class SessionListPage(BaseModel):
    items: list[SessionOut]
    next_cursor: str | None = None
