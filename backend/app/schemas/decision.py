"""Decision (ADR-lite) schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DecisionIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=400)
    context: str | None = Field(default=None, max_length=20_000)
    decision: str = Field(..., min_length=1, max_length=20_000)
    consequences: str | None = Field(default=None, max_length=20_000)
    reconsider_if: str | None = Field(default=None, max_length=2_000)


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    created_at: datetime
    title: str
    context: str | None = None
    decision: str
    consequences: str | None = None
    reconsider_if: str | None = None
