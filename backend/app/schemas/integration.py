from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class IntegrationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    connected_at: datetime
    config: dict[str, Any]


class GitHubRepoOut(BaseModel):
    owner: str
    name: str
    full_name: str
    description: str | None = None
    private: bool
    default_branch: str
    language: str | None = None
    license_spdx: str | None = None
    homepage: str | None = None
    clone_url: str
    pushed_at: datetime | None = None


class ImportItem(BaseModel):
    owner: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    as_slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]{0,48}[a-z0-9]$")


class ImportRequest(BaseModel):
    repos: list[ImportItem] = Field(..., min_length=1, max_length=100)


class ImportResultItem(BaseModel):
    owner: str
    name: str
    slug: str | None
    status: str  # "imported" | "skipped-duplicate" | "failed"
    detail: str | None = None


class ImportResponse(BaseModel):
    results: list[ImportResultItem]
