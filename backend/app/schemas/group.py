from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class GroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name: str
    color: str | None = None
    position: int


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")
    color: str | None = Field(default=None, max_length=20)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = Field(default=None, max_length=20)
    position: int | None = None


class ReorderItem(BaseModel):
    slug: str
    group_id: str | None = None
    position: int


class ReorderRequest(BaseModel):
    items: list[ReorderItem] = Field(..., max_length=500)


class ReorderResult(BaseModel):
    updated: int
