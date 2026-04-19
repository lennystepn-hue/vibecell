from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$"
_VALID_STATUSES = {"idea", "building", "live", "paused", "shipped", "archived", "dead"}


class ProjectListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    name: str
    emoji: str | None = None
    color: str | None = None
    pitch: str | None = None
    status: str


class ProjectOut(ProjectListItem):
    # Full project detail, without children (children arrive in Phase 6).
    is_public: int
    archived_at: str | None = None


class ProjectListPage(BaseModel):
    items: list[ProjectListItem]
    next_cursor: str | None = None


class ProjectCreate(BaseModel):
    slug: str = Field(..., pattern=_SLUG_RE, min_length=2, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=20)
    pitch: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="building")

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    emoji: str | None = Field(default=None, max_length=16)
    color: str | None = Field(default=None, max_length=20)
    pitch: str | None = Field(default=None, max_length=2000)
    status: str | None = None
    is_public: int | None = None

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(_VALID_STATUSES)}")
        return v
