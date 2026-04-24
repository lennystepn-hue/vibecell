"""MCP tool registry — 22 tools (vibecell.run excluded)."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

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
    current_focus: str | None = None  # optional override; default auto-derived from summary


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


# ---- TODO args ----

class TodoListArgs(BaseModel):
    project: str | None = None
    include_done: bool = False


class TodoAddArgs(BaseModel):
    title: str = Field(..., min_length=1, max_length=2000)
    body: str | None = None
    batch: str | None = Field(default=None, max_length=120)
    project: str | None = None


class TodoBatchAddArgs(BaseModel):
    batch: str = Field(..., min_length=1, max_length=120)
    titles: list[str] = Field(..., min_length=1, max_length=50)
    project: str | None = None


class TodoIdArgs(BaseModel):
    todo_id: str
    project: str | None = None


class TodoCompleteArgs(BaseModel):
    todo_id: str
    completion_note: str | None = Field(default=None, max_length=2000)
    project: str | None = None


class TodoMatchArgs(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    auto_complete: bool = False
    project: str | None = None


# ---- AI args (BYOK — uses user's stored ANTHROPIC_API_KEY) ----

class AIPlanTodosArgs(BaseModel):
    goal: str = Field(..., min_length=3, max_length=2000)
    commit: bool = True
    project: str | None = None


class AILaunchCopyArgs(BaseModel):
    ship_id: str | None = None
    platforms: list[str] = Field(
        default_factory=lambda: ["twitter_x", "linkedin", "indiehackers", "product_hunt"],
    )
    project: str | None = None


class AIRetroArgs(BaseModel):
    project: str | None = None


class AIResumeBriefArgs(BaseModel):
    project: str | None = None


# ---- Repo sync / drift args ----

class SyncRepoArgs(BaseModel):
    """Scan a local repo to populate stack/infra/tags/pitch + fingerprint manifests.

    The MCP server can't read the client's filesystem, so the client (Claude) reads
    the curated list of manifest files locally with its Read tool and sends their
    content here. The server computes SHA-256 fingerprints + runs Haiku enrichment.
    """
    local_path: str = Field(..., min_length=1, max_length=1024)
    manifests: dict[str, str] = Field(
        default_factory=dict,
        description="{filename: content} e.g. {'package.json': '...', 'pyproject.toml': '...'}. "
                    "Max 8000 chars per file.",
    )
    slug: str | None = None  # defaults to active
    force: bool = False  # if True, re-enrich even when no drift detected


class CheckEnvDriftArgs(BaseModel):
    """Compare fresh manifest contents against the stored fingerprint — read-only."""

    manifests: dict[str, str] = Field(
        default_factory=dict,
        description="Same shape as vibecell_sync_repo.manifests.",
    )
    slug: str | None = None


class AddEnvironmentArgs(BaseModel):
    """Attach or update a ProjectEnvironment row."""

    kind: str = Field(..., description="local | staging | prod | preview | edge | …")
    url: str = Field(..., min_length=1, max_length=2000)
    env_template_path: str | None = None
    db_alias: str | None = None
    slug: str | None = None


class AddLinkArgs(BaseModel):
    """Attach or update a ProjectLink row. Dedups by URL."""

    kind: str = Field(default="other", description="docs | api | metrics | admin | live | github | other")
    label: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=2000)
    slug: str | None = None


class AddCommandArgs(BaseModel):
    """Attach or update a ProjectCommand row. Dedups by label (case-insensitive)."""

    label: str = Field(..., min_length=1, max_length=200)
    command: str = Field(..., min_length=1, max_length=4000)
    run_in: str = Field(default="terminal", description="terminal | browser")
    confirm_required: bool = False
    slug: str | None = None


class CreateProjectArgs(BaseModel):
    """Spawn a new project from a concept, fully populated."""

    name: str = Field(..., min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=50)
    pitch: str | None = Field(default=None, max_length=2000)
    emoji: str | None = Field(default=None, max_length=16)
    status: str | None = Field(default="idea")
    group: str | None = Field(
        default=None,
        description="Group name or ID. Auto-created if a name is given and doesn't exist.",
    )
    github_url: str | None = None
    tags: list[str] = Field(default_factory=list)
    stack: list[dict] = Field(
        default_factory=list,
        description="[{slug, name, kind, role}] — same shape as enrichment stack.",
    )
    infra: dict = Field(
        default_factory=dict,
        description="{db, server_alias, dns_provider, cdn, object_storage}",
    )
    environments: list[dict] = Field(
        default_factory=list,
        description="[{kind: 'local'|'staging'|'prod', url, env_template_path?}]",
    )
    commands: list[dict] = Field(
        default_factory=list,
        description="[{label, command, run_in: 'terminal'}]",
    )
    links: list[dict] = Field(
        default_factory=list,
        description="[{kind, label, url}] — docs, api, metrics, etc. (github/homepage handled separately)",
    )
    switch_to_active: bool = Field(
        default=True,
        description="Set this project as the active one after creation.",
    )


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
    Tool("vibecell_ping", "Health check. Returns ok=true + version + active project slug.", NoArgs, r.handle_ping),
    Tool("vibecell_active", "Return the currently-active project's full aggregate. Always call this at session start.", NoArgs, r.handle_active),
    Tool("vibecell_list", "List projects in the active workspace. Optional filters: status, tag, q.", ListArgs, r.handle_list),
    Tool("vibecell_get", "Return the full aggregate for a single project by slug.", SlugRequired, r.handle_get),
    Tool("vibecell_brief", "Resurrection brief for a project. Defaults to active.", SlugArg, r.handle_brief),
    Tool("vibecell_search", "Federated full-text search across the workspace.", SearchArgs, r.handle_search),
    Tool("vibecell_recent_projects", "Return up to n projects ordered by sidebar position.", RecentArgs, r.handle_recent),
    Tool("vibecell_claude_md", "Generate a CLAUDE.md-ready markdown brief for a project.", SlugArg, r.handle_claude_md),
    Tool("vibecell_handover", "Longer prose onboarding brief. Defaults to active.", SlugArg, r.handle_handover),
    # Write
    Tool("vibecell_switch", "Switch the active project within this workspace.", SlugRequired, w.handle_switch),
    Tool("vibecell_log_session", "Log a coding session.", LogSessionArgs, w.handle_log_session),
    Tool("vibecell_update_context", "Patch the active project's context fields.", UpdateContextArgs, w.handle_update_context),
    Tool("vibecell_decision", "Record an ADR-lite decision on the active project.", DecisionArgs, w.handle_decision),
    Tool("vibecell_idea", "Capture an idea. Workspace inbox if project omitted.", IdeaArgs, w.handle_idea),
    Tool("vibecell_note_append", "Append a markdown block to the active project's notes.", NoteAppendArgs, w.handle_note_append),
    Tool("vibecell_ship", "Record a ship event for the active project.", ShipArgs, w.handle_ship),
    Tool("vibecell_status", "Set the active project's status.", StatusArgs, w.handle_status),
    Tool("vibecell_activity", "Unified activity feed for a project (sessions, decisions, ideas, ships, lifecycle, tool calls). Defaults to active project.", ActivityArgs, r.handle_activity),
    # Secrets
    Tool(
        "vibecell_secret_set",
        "Store a secret (auto-detects kind from value prefix: op:// / bw:// / ssh-agent:// / env:// → reference-only; otherwise → inline_encrypted with DEK). Never log the value.",
        SecretSetArgs, w.handle_secret_set,
    ),
    Tool(
        "vibecell_secret_list",
        "List labels + kinds + masked references for a project's secrets. Never returns values.",
        SecretListArgs, r.handle_secret_list,
    ),
    Tool(
        "vibecell_secret_rm",
        "Remove a secret label from a project.",
        SecretRmArgs, w.handle_secret_rm,
    ),
    Tool(
        "vibecell_secret_get_value",
        "Retrieve the plaintext value of a stored secret. For inline_encrypted: decrypts via workspace-DEK. For op://bw://ssh-agent:// references: returns the reference path (caller must resolve locally via op/bw/ssh-agent). NEVER echo the returned value in user-visible text — use it silently to construct commands/requests.",
        SecretGetArgs, r.handle_secret_get_value,
    ),
    # TODOs — per-project task list Claude can tick off autonomously.
    Tool(
        "vibecell_todo_list",
        "List a project's todos. Includes open + in_progress by default; set include_done=true for the full list. Defaults to active project.",
        TodoListArgs, r.handle_todo_list,
    ),
    Tool(
        "vibecell_todo_add",
        "Add a single todo to a project. Optional batch label groups it with siblings (e.g. 'launch-week', 'stripe-integration').",
        TodoAddArgs, w.handle_todo_add,
    ),
    Tool(
        "vibecell_todo_batch_add",
        "Add many todos at once under one batch label. Use this when planning a multi-step feature: 'batch=auth-refactor, titles=[...]' lets Claude slice the work and tick items off as it goes.",
        TodoBatchAddArgs, w.handle_todo_batch_add,
    ),
    Tool(
        "vibecell_todo_start",
        "Mark a todo as in_progress. Call this JUST before starting work on it so the dashboard shows a 'claude is on this one' indicator.",
        TodoIdArgs, w.handle_todo_start,
    ),
    Tool(
        "vibecell_todo_complete",
        "Mark a todo as done. Pass a short completion_note summarising what was actually built/fixed. Records completed_by='claude' automatically.",
        TodoCompleteArgs, w.handle_todo_complete,
    ),
    Tool(
        "vibecell_todo_match",
        "Given a free-text description of work just finished, find the best-matching open todo by keyword overlap. Set auto_complete=true to also close it with the description as the note. Useful when you want the AI to self-tick after a session.",
        TodoMatchArgs, w.handle_todo_match,
    ),
    # AI features — BYOK (Bring Your Own Key). Uses the project's stored
    # ANTHROPIC_API_KEY secret, falls back to the platform-level key.
    Tool(
        "vibecell_ai_plan_todos",
        "Break a free-text goal into a batch of concrete todos and persist them. Uses the user's own Anthropic key (via secret ANTHROPIC_API_KEY) for planning. Set commit=false to preview titles without saving.",
        AIPlanTodosArgs, w.handle_ai_plan_todos,
    ),
    Tool(
        "vibecell_ai_launch_copy",
        "Generate launch copy for a ship event — Twitter/X, LinkedIn, IndieHackers, ProductHunt — using the user's own Anthropic key. Defaults to the latest ship if ship_id omitted.",
        AILaunchCopyArgs, w.handle_ai_launch_copy,
    ),
    Tool(
        "vibecell_ai_retro",
        "Generate a one-page markdown retrospective (Worked / Didn't / Next-time) from sessions + decisions since the last ship.",
        AIRetroArgs, w.handle_ai_retro,
    ),
    Tool(
        "vibecell_ai_resume_brief",
        "Generate the funny 'where the fuck was I' morning-brief — ~150 words summarising last session + next step + open questions + a single concrete action to take first.",
        AIResumeBriefArgs, w.handle_ai_resume_brief,
    ),
    # Repo sync / drift — THE session-start workhorse.
    Tool(
        "vibecell_sync_repo",
        "Scan a local repo: persist local_path, enrich stack/infra/tags/pitch from manifests, "
        "and store SHA-256 fingerprints so drift can be detected on the next session. "
        "The client reads manifest files (package.json, pyproject.toml, Dockerfile, "
        "compose.yml, README.md, etc.) and passes {path: content} via 'manifests'. "
        "Smart: on first call → full enrich; on subsequent calls → only re-enrich if drift "
        "detected (or force=true). Call this ONCE per session when vibecell_active says "
        "env_status.needs_initial_scan=true, or whenever you notice stack/infra are empty.",
        SyncRepoArgs, w.handle_sync_repo,
    ),
    Tool(
        "vibecell_audit",
        "Return a structured audit of what's stale / unsynced / missing on the active "
        "project: empty pitch, missing stack, no environments, empty current_focus, "
        "stale sessions, never-scanned env, etc. Each gap has {kind, message, action} "
        "so Claude knows exactly which tool to call next to fix it. ALWAYS call this "
        "early in every session after vibecell_active — it's your pre-flight checklist.",
        SlugArg, r.handle_audit,
    ),
    Tool(
        "vibecell_check_env_drift",
        "Read-only check: compare fresh manifest contents against the stored fingerprint. "
        "Returns {drifted, never_scanned, changed_files, new_files, removed_files, last_scanned}. "
        "Use this when you want to know 'did my env change?' without triggering a re-enrichment. "
        "If you want to REFRESH stack/infra when drift is detected, call vibecell_sync_repo instead.",
        CheckEnvDriftArgs, r.handle_check_env_drift,
    ),
    Tool(
        "vibecell_add_environment",
        "Attach or update a ProjectEnvironment (local / staging / prod / preview). Idempotent: "
        "if an environment with the same kind already exists we UPDATE its URL + env_template_path "
        "rather than inserting a duplicate. Use this when the user or Claude deploys somewhere new "
        "mid-project ('I just deployed staging at https://staging.foo.com').",
        AddEnvironmentArgs, w.handle_add_environment,
    ),
    Tool(
        "vibecell_add_link",
        "Attach or update a ProjectLink (docs / api / metrics / admin / live / other). Idempotent: "
        "dedups by URL — if the same URL already exists on the project we update its label + kind "
        "instead of duplicating. Use this for adding non-github/non-homepage URLs — 'the API docs "
        "live at …', 'Prometheus dashboard is at …', 'admin is at …'.",
        AddLinkArgs, w.handle_add_link,
    ),
    Tool(
        "vibecell_add_command",
        "Attach or update a ProjectCommand (runnable script, e.g. 'pnpm dev' / 'make deploy'). "
        "Idempotent: dedups by label (case-insensitive). Use this when a new script is added to "
        "package.json / Makefile / justfile and you want the user to see it in the project's "
        "Commands card.",
        AddCommandArgs, w.handle_add_command,
    ),
    Tool(
        "vibecell_create_project",
        "Create a brand-new Vibecell project from a concept — in ONE call. Use this when the user "
        "describes a new idea ('I want to build X', 'let's start a new project called Y', 'create a "
        "project for Z') — gather name + pitch + any stack/tags/envs/commands/links/emoji you can "
        "infer from the conversation, then call this tool. It provisions the project, applies the "
        "enrichment pipeline (idempotent dedup), optionally creates a group, optionally records a "
        "GitHub URL, and sets the new project as active by default. Returns the slug + a URL the "
        "user can open immediately.",
        CreateProjectArgs, w.handle_create_project,
    ),
]

TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}

# Back-compat alias: old clients (Claude Code sessions that connected when the
# tool names had dots — e.g. "vibecell.ping") still send the dotted form on
# tools/call. Accept both by mapping dots → underscores transparently in the
# dispatcher. Claude Desktop rejects dots in tool names per its schema
# validation (^[a-zA-Z0-9_-]{1,64}$), so tools/list returns only the
# underscore form.
def resolve_tool(name: str) -> Tool | None:
    """Look up a tool by canonical (underscore) name OR legacy dotted name."""
    if name in TOOLS_BY_NAME:
        return TOOLS_BY_NAME[name]
    # Accept "vibecell.foo" → "vibecell_foo" (only the first dot, to avoid
    # mangling user-supplied arguments that happen to contain dots).
    if "." in name:
        underscore = name.replace(".", "_", 1)
        return TOOLS_BY_NAME.get(underscore)
    return None
