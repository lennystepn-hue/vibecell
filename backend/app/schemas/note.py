"""Project notes (singleton markdown scratchpad) schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    markdown: str = ""
    updated_at: datetime | None = None


class NoteUpdate(BaseModel):
    markdown: str = Field(default="", max_length=200_000)
