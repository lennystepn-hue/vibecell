"""MCP tool registry — 22 tools (vibecell.run excluded)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from pydantic import BaseModel, Field

from app.mcp.auth import MCPContext
from app.mcp.handlers import read as r
from app.mcp.handlers import write as w


# ---- Argument schemas ----

class NoArgs(BaseModel):
    pass


class SlugArg(BaseModel):
    slug: str | None = None


class SlugRequired(BaseModel):
    slug: str


class ListArgs(BaseModel):
    status: str | None = None
    tag: str | None = None
    q: str | None = None


class SearchArgs(BaseModel):
    q: str
    limit: int = 50


class RecentArgs(BaseModel):
    n: int = 5


class LogSessionArgs(BaseModel):
    summary: str
    files_touched: list[str] = Field(default_factory=list)
    commits: list[dict] = Field(default_factory=list)
    next_step: str | None = None


class UpdateContextArgs(BaseModel):
    current_focus: str | None = None
    next_step: str | None = None
    user_wants: str | None = None
    open_questions: list[str] | None = None
    known_issues: list[str] | None = None
    blocked_by: str | None = None


class DecisionArgs(BaseModel):
    title: str
    decision: str
    context: str | None = None
    consequences: str | None = None
    reconsider_if: str | None = None


class IdeaArgs(BaseModel):
    body: str
    project: str | None = None


class NoteAppendArgs(BaseModel):
    markdown: str


class ShipArgs(BaseModel):
    version: str | None = None
    summary: str | None = None
    changelog_md: str | None = None


class StatusArgs(BaseModel):
    status: str


class ActivityArgs(BaseModel):
    slug: str | None = None
    limit: int = 50


class SecretSetArgs(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    value: str = Field(..., min_length=1)  # the secret OR a reference like op://... / bw://...
    project: str | None = None  # slug; defaults to active project


class SecretListArgs(BaseModel):
    project: str | None = None


class SecretRmArgs(BaseModel):
    label: str
    project: str | None = None


class SecretGetArgs(BaseModel):
    label: str
    project: str | None = None


# ---- Registry ----

Handler = Callable[[BaseModel, MCPContext], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Handler


TOOLS: list[Tool] = [
    # Read
    Tool("vibecell.ping", "Health check. Returns ok=true + version + active project slug.", NoArgs, r.handle_ping),
    Tool("vibecell.active", "Return the currently-active project's full aggregate. Always call this at session start.", NoArgs, r.handle_active),
    Tool("vibecell.list", "List projects in the active workspace. Optional filters: status, tag, q.", ListArgs, r.handle_list),
    Tool("vibecell.get", "Return the full aggregate for a single project by slug.", SlugRequired, r.handle_get),
    Tool("vibecell.brief", "Resurrection brief for a project. Defaults to active.", SlugArg, r.handle_brief),
    Tool("vibecell.search", "Federated full-text search across the workspace.", SearchArgs, r.handle_search),
    Tool("vibecell.recent_projects", "Return up to n projects ordered by sidebar position.", RecentArgs, r.handle_recent),
    Tool("vibecell.claude_md", "Generate a CLAUDE.md-ready markdown brief for a project.", SlugArg, r.handle_claude_md),
    Tool("vibecell.handover", "Longer prose onboarding brief. Defaults to active.", SlugArg, r.handle_handover),
    # Write
    Tool("vibecell.switch", "Switch the active project within this workspace.", SlugRequired, w.handle_switch),
    Tool("vibecell.log_session", "Log a coding session.", LogSessionArgs, w.handle_log_session),
    Tool("vibecell.update_context", "Patch the active project's context fields.", UpdateContextArgs, w.handle_update_context),
    Tool("vibecell.decision", "Record an ADR-lite decision on the active project.", DecisionArgs, w.handle_decision),
    Tool("vibecell.idea", "Capture an idea. Workspace inbox if project omitted.", IdeaArgs, w.handle_idea),
    Tool("vibecell.note_append", "Append a markdown block to the active project's notes.", NoteAppendArgs, w.handle_note_append),
    Tool("vibecell.ship", "Record a ship event for the active project.", ShipArgs, w.handle_ship),
    Tool("vibecell.status", "Set the active project's status.", StatusArgs, w.handle_status),
    Tool("vibecell.activity", "Unified activity feed for a project (sessions, decisions, ideas, ships, lifecycle, tool calls). Defaults to active project.", ActivityArgs, r.handle_activity),
    # Secrets
    Tool(
        "vibecell.secret_set",
        "Store a secret (auto-detects kind from value prefix: op:// / bw:// / ssh-agent:// / env:// → reference-only; otherwise → inline_encrypted with DEK). Never log the value.",
        SecretSetArgs, w.handle_secret_set,
    ),
    Tool(
        "vibecell.secret_list",
        "List labels + kinds + masked references for a project's secrets. Never returns values.",
        SecretListArgs, r.handle_secret_list,
    ),
    Tool(
        "vibecell.secret_rm",
        "Remove a secret label from a project.",
        SecretRmArgs, w.handle_secret_rm,
    ),
    Tool(
        "vibecell.secret_get_value",
        "Retrieve the plaintext value of a stored secret. For inline_encrypted: decrypts via workspace-DEK. For op://bw://ssh-agent:// references: returns the reference path (caller must resolve locally via op/bw/ssh-agent). NEVER echo the returned value in user-visible text — use it silently to construct commands/requests.",
        SecretGetArgs, r.handle_secret_get_value,
    ),
]

TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}
