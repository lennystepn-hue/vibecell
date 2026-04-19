"""LifecycleEvent schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LifecycleEventIn(BaseModel):
    at: datetime
    kind: str = Field(..., min_length=1, max_length=50)
    detail: dict[str, Any] | None = None


class LifecycleEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    at: datetime
    kind: str
    detail: dict[str, Any] | None = None
