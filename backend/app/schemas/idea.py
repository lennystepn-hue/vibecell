"""Idea (workspace inbox) schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IdeaStatus = Literal["inbox", "triaged", "discarded"]
IdeaSource = Literal["web", "ios", "email", "skill", "cli"]


class IdeaIn(BaseModel):
    body: str = Field(..., min_length=1, max_length=20_000)
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    source: IdeaSource | None = None


class IdeaUpdate(BaseModel):
    status: IdeaStatus | None = None
    project_id: str | None = Field(default=None, min_length=26, max_length=26)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)


class IdeaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    project_id: str | None = None
    captured_at: datetime
    body: str
    source: str | None = None
    status: str
