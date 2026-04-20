from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.tag import TagOut as TagOut  # re-export for consumers that imported from here

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
    group_id: str | None = None
    position: int = 0
    github_url: str | None = None


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


# --- Child sub-resource schemas ---


class RepoIn(BaseModel):
    role: str | None = Field(default=None, max_length=20)
    git_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, max_length=100)
    local_path: str | None = Field(default=None, max_length=500)
    primary_lang: str | None = Field(default=None, max_length=50)
    license: str | None = Field(default=None, max_length=50)


class RepoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str | None = None
    git_url: str | None = None
    default_branch: str | None = None
    local_path: str | None = None
    primary_lang: str | None = None
    license: str | None = None


class EnvironmentIn(BaseModel):
    kind: str = Field(..., pattern=r"^(local|preview|staging|prod)$")
    url: str | None = Field(default=None, max_length=500)
    env_template_path: str | None = Field(default=None, max_length=500)
    db_alias: str | None = Field(default=None, max_length=100)


class EnvironmentUpdate(BaseModel):
    kind: str | None = Field(default=None, pattern=r"^(local|preview|staging|prod)$")
    url: str | None = Field(default=None, max_length=500)
    env_template_path: str | None = Field(default=None, max_length=500)
    db_alias: str | None = Field(default=None, max_length=100)


class EnvironmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    url: str | None = None
    env_template_path: str | None = None
    db_alias: str | None = None


class InfraUpsert(BaseModel):
    server_alias: str | None = Field(default=None, max_length=100)
    domain_primary: str | None = Field(default=None, max_length=255)
    domains: list[str] | None = None
    dns_provider: str | None = Field(default=None, max_length=50)
    db_host: str | None = Field(default=None, max_length=255)
    cdn: str | None = Field(default=None, max_length=50)
    object_storage: str | None = Field(default=None, max_length=255)


class InfraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    server_alias: str | None = None
    domain_primary: str | None = None
    domains: list[str] = []
    dns_provider: str | None = None
    db_host: str | None = None
    cdn: str | None = None
    object_storage: str | None = None


class ContextOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list[Any] = []
    known_issues: list[Any] = []
    blocked_by: str | None = None


class ContextUpsert(BaseModel):
    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list[Any] | None = None
    known_issues: list[Any] | None = None
    blocked_by: str | None = None


class LinkIn(BaseModel):
    kind: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    url: str = Field(..., min_length=1, max_length=1000)


class LinkUpdate(BaseModel):
    kind: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, min_length=1, max_length=1000)


class LinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str | None = None
    label: str | None = None
    url: str


class CommandIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    command: str = Field(..., min_length=1, max_length=2000)
    run_in: str = Field(default="terminal", pattern=r"^(terminal|background)$")
    confirm_required: int = 1


class CommandUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    command: str | None = Field(default=None, min_length=1, max_length=2000)
    run_in: str | None = Field(default=None, pattern=r"^(terminal|background)$")
    confirm_required: int | None = None


class CommandOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    command: str
    run_in: str
    confirm_required: int


class StackAttachIn(BaseModel):
    stack_item_slug: str = Field(..., min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=20)


class StackOut(BaseModel):
    stack_item_slug: str
    name: str
    kind: str | None = None
    role: str | None = None


class TagAttachIn(BaseModel):
    tag_id: str | None = None
    name: str | None = Field(default=None, max_length=100)
    color: str | None = Field(default=None, max_length=20)


class ProjectFullOut(ProjectOut):
    """Project detail + nested children. Used by GET /projects/:slug."""

    context: ContextOut | None = None
    infra: InfraOut | None = None
    repos: list[RepoOut] = []
    environments: list[EnvironmentOut] = []
    links: list[LinkOut] = []
    commands: list[CommandOut] = []
    stack: list[StackOut] = []
    tags: list[TagOut] = []
