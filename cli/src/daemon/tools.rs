//! MCP tool specs + dispatcher. 14 tools covering the core read/write surface
//! Claude Code needs to drive Hangar during a coding session.
//!
//! Stubbed tools (log_session / decision / idea / note_append) return success
//! but stash data into workaround fields because the sessions / decisions /
//! ideas / notes tables aren't in Spec 1. They all carry TODO(spec-2) markers
//! for when the real tables land.

use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

use crate::daemon::mcp::AppState;

// ---------------------------------------------------------------------------
// Tool specs (served by GET /mcp/v1/tools/list)
// ---------------------------------------------------------------------------

pub fn tool_specs() -> Value {
    json!([
        {
            "name": "hangar.ping",
            "description": "Health check. Returns ok=true + version + active project slug.",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "hangar.active",
            "description": "Return the currently-active project's full aggregate (name, pitch, status, context, stack, links, commands, etc). Always call this at session start.",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "hangar.list",
            "description": "List projects in the active workspace. Optional filters: status, tag, q (full-text).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "tag": {"type": "string"},
                    "q": {"type": "string"}
                }
            }
        },
        {
            "name": "hangar.get",
            "description": "Return the full aggregate for a single project by slug.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"]
            }
        },
        {
            "name": "hangar.brief",
            "description": "Generate a human-readable resurrection brief for a project (name, pitch, status, current focus, next step, suggested first move). Defaults to active project.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}}
            }
        },
        {
            "name": "hangar.search",
            "description": "Search projects by substring (ilike on name / pitch).",
            "inputSchema": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"]
            }
        },
        {
            "name": "hangar.recent_projects",
            "description": "Return up to n projects (default 5) ordered by sidebar position (proxy for recently-touched until sessions land).",
            "inputSchema": {
                "type": "object",
                "properties": {"n": {"type": "integer"}}
            }
        },
        {
            "name": "hangar.switch",
            "description": "Switch the active project. Subsequent calls to hangar.active / hangar.brief default to this slug.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"]
            }
        },
        {
            "name": "hangar.log_session",
            "description": "Log a session summary. TODO(spec-2): will write to sessions table. For now, writes summary to context.current_focus and next_step to context.next_step.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "files_touched": {"type": "array", "items": {"type": "string"}},
                    "commits": {"type": "array"},
                    "next_step": {"type": "string"}
                },
                "required": ["summary"]
            }
        },
        {
            "name": "hangar.update_context",
            "description": "Patch the active project's context fields (current_focus, next_step, user_wants, open_questions, known_issues, blocked_by).",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "current_focus": {"type": "string"},
                    "next_step": {"type": "string"},
                    "user_wants": {"type": "string"},
                    "open_questions": {"type": "array"},
                    "known_issues": {"type": "array"},
                    "blocked_by": {"type": "string"}
                }
            }
        },
        {
            "name": "hangar.decision",
            "description": "Record an architectural decision. TODO(spec-2): will write to decisions table. For now, appends to context.known_issues as 'DECISION [title]: decision'.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "context": {"type": "string"},
                    "decision": {"type": "string"},
                    "consequences": {"type": "string"},
                    "reconsider_if": {"type": "string"}
                },
                "required": ["title", "decision"]
            }
        },
        {
            "name": "hangar.idea",
            "description": "Capture an idea for the active project. TODO(spec-2): will write to ideas table. For now, appends to context.open_questions prefixed 'IDEA: '.",
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        },
        {
            "name": "hangar.note_append",
            "description": "Append a markdown note to the active project. TODO(spec-2): will write to notes table. For now, appends to pitch (truncated to 2000 chars).",
            "inputSchema": {
                "type": "object",
                "properties": {"markdown": {"type": "string"}},
                "required": ["markdown"]
            }
        },
        {
            "name": "hangar.status",
            "description": "Set the active project's status (idea | building | live | paused | shipped | archived | dead).",
            "inputSchema": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
                "required": ["status"]
            }
        }
    ])
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

pub async fn dispatch(state: &AppState, name: &str, args: &Value) -> Result<String> {
    match name {
        "hangar.ping" => ping(state).await,
        "hangar.active" => active(state).await,
        "hangar.list" => list(state, args).await,
        "hangar.get" => get_project(state, args).await,
        "hangar.brief" => brief(state, args).await,
        "hangar.search" => search(state, args).await,
        "hangar.recent_projects" => recent_projects(state, args).await,
        "hangar.switch" => switch(state, args).await,
        "hangar.log_session" => log_session(state, args).await,
        "hangar.update_context" => update_context(state, args).await,
        "hangar.decision" => decision(state, args).await,
        "hangar.idea" => idea(state, args).await,
        "hangar.note_append" => note_append(state, args).await,
        "hangar.status" => set_status(state, args).await,
        _ => bail!("unknown tool: {name}"),
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

fn arg_str<'a>(args: &'a Value, field: &str) -> Option<&'a str> {
    args.get(field).and_then(|v| v.as_str())
}

fn arg_str_required<'a>(args: &'a Value, field: &str) -> Result<&'a str> {
    arg_str(args, field).with_context(|| format!("missing required arg `{field}`"))
}

async fn resolve_slug(state: &AppState, args: &Value) -> Result<String> {
    if let Some(s) = arg_str(args, "slug") {
        return Ok(s.to_string());
    }
    active_slug_from_cloud(state).await
}

/// Active slug — prefer cached, fall back to scanning `/api/v1/me` or just
/// the first project. Spec 1 does not expose `GET /active-project`, so we
/// approximate: single-user workspaces almost always have 1 project; for more
/// we check the cache's `active_project` row (written by hangar.switch).
async fn active_slug_from_cloud(_state: &AppState) -> Result<String> {
    let conn = crate::cache::open()?;
    if let Some(slug) = crate::cache::get_active_slug(&conn)? {
        return Ok(slug);
    }
    // Fall back to the first project in the cache — most helpful for a fresh
    // machine where sync ran but switch hasn't been called yet.
    let projects = crate::cache::list_projects(&conn)?;
    if let Some(first) = projects.into_iter().next() {
        return Ok(first.slug);
    }
    bail!("no active project — call hangar.switch(slug) or hangar sync first")
}

// ---------------------------------------------------------------------------
// Read tools
// ---------------------------------------------------------------------------

async fn ping(_state: &AppState) -> Result<String> {
    let active = crate::cache::open()
        .ok()
        .and_then(|c| crate::cache::get_active_slug(&c).ok().flatten());
    Ok(json!({
        "ok": true,
        "version": env!("CARGO_PKG_VERSION"),
        "active_slug": active,
    })
    .to_string())
}

async fn active(state: &AppState) -> Result<String> {
    let slug = active_slug_from_cloud(state).await?;
    let full = state.cloud.get_project(&slug).await?;
    Ok(full.to_string())
}

async fn list(state: &AppState, args: &Value) -> Result<String> {
    let status = arg_str(args, "status");
    let tag = arg_str(args, "tag");
    let q = arg_str(args, "q");
    let page = state.cloud.list_projects(status, tag, q, Some(200)).await?;
    // Flatten to just the items array for a tighter response.
    let items = page.get("items").cloned().unwrap_or(json!([]));
    Ok(items.to_string())
}

async fn get_project(state: &AppState, args: &Value) -> Result<String> {
    let slug = arg_str_required(args, "slug")?;
    let full = state.cloud.get_project(slug).await?;
    Ok(full.to_string())
}

async fn brief(state: &AppState, args: &Value) -> Result<String> {
    let slug = resolve_slug(state, args).await?;
    let full = state.cloud.get_project(&slug).await?;

    let name = full.get("name").and_then(|v| v.as_str()).unwrap_or(&slug);
    let pitch = full
        .get("pitch")
        .and_then(|v| v.as_str())
        .unwrap_or("(no pitch yet)");
    let status = full
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("idea");
    let ctx = full.get("context").cloned().unwrap_or(json!({}));
    let current_focus = ctx
        .get("current_focus")
        .and_then(|v| v.as_str())
        .unwrap_or("(unset)");
    let next_step = ctx
        .get("next_step")
        .and_then(|v| v.as_str())
        .unwrap_or("(unset)");
    let open_q = ctx
        .get("open_questions")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect::<Vec<_>>()
                .join("; ")
        })
        .unwrap_or_default();
    let open_q_display = if open_q.is_empty() {
        "(none)".to_string()
    } else {
        open_q
    };

    let suggested = if next_step != "(unset)" {
        format!("Pick up where you left off: {next_step}")
    } else if current_focus != "(unset)" {
        format!("Continue current focus: {current_focus}")
    } else {
        "Run hangar.update_context to capture what you want to do next.".to_string()
    };

    let brief = format!(
        "Project {name} — {pitch}.\n\n\
         What it is: {pitch}\n\n\
         Where it stands: status={status}. Focus: {current_focus}.\n\n\
         What you were about to do: {next_step}. Open questions: {open_q_display}.\n\n\
         Suggested first move: {suggested}"
    );
    Ok(brief)
}

async fn search(state: &AppState, args: &Value) -> Result<String> {
    let q = arg_str_required(args, "q")?;
    let page = state
        .cloud
        .list_projects(None, None, Some(q), Some(200))
        .await?;
    let items = page.get("items").cloned().unwrap_or(json!([]));
    Ok(items.to_string())
}

async fn recent_projects(state: &AppState, args: &Value) -> Result<String> {
    let n = args.get("n").and_then(|v| v.as_u64()).unwrap_or(5) as usize;
    let page = state
        .cloud
        .list_projects(None, None, None, Some(200))
        .await?;
    let items = page
        .get("items")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let trimmed: Vec<Value> = items.into_iter().take(n).collect();
    Ok(json!(trimmed).to_string())
}

// ---------------------------------------------------------------------------
// Write tools
// ---------------------------------------------------------------------------

async fn switch(state: &AppState, args: &Value) -> Result<String> {
    let slug = arg_str_required(args, "slug")?;
    let out = state.cloud.switch_project(slug).await?;
    // Mirror into local cache so hangar.active / hangar.ping see the change.
    if let Ok(conn) = crate::cache::open() {
        // workspace_id is not part of the /switch response — we scope by the
        // currently-paired workspace, read from /me on first call. Use a
        // stable placeholder key if me() fails.
        let ws_id = state
            .cloud
            .me()
            .await
            .ok()
            .and_then(|m| {
                m.get("active_workspace")
                    .and_then(|w| w.get("id"))
                    .and_then(|v| v.as_str())
                    .map(str::to_string)
            })
            .unwrap_or_else(|| "default".to_string());
        let _ = crate::cache::set_active_project(&conn, &ws_id, slug);
    }
    Ok(out.to_string())
}

// TODO(spec-2): replace with POST /sessions once the sessions table exists.
async fn log_session(state: &AppState, args: &Value) -> Result<String> {
    let summary = arg_str_required(args, "summary")?;
    let next_step = arg_str(args, "next_step");
    let slug = resolve_slug(state, args).await?;
    let mut patch = json!({"current_focus": summary});
    if let Some(ns) = next_step {
        patch["next_step"] = json!(ns);
    }
    let result = state.cloud.patch_context(&slug, &patch).await?;
    Ok(json!({
        "ok": true,
        "stub": "spec-2",
        "note": "session logged into context.current_focus + next_step until sessions table exists",
        "context": result
    })
    .to_string())
}

async fn update_context(state: &AppState, args: &Value) -> Result<String> {
    let slug = resolve_slug(state, args).await?;
    // Forward the whole args object as the patch body — backend validates.
    let mut body = args.clone();
    if let Some(obj) = body.as_object_mut() {
        obj.remove("slug");
    }
    let out = state.cloud.patch_context(&slug, &body).await?;
    Ok(out.to_string())
}

// TODO(spec-2): replace with POST /decisions.
async fn decision(state: &AppState, args: &Value) -> Result<String> {
    let title = arg_str_required(args, "title")?;
    let decision = arg_str_required(args, "decision")?;
    let slug = resolve_slug(state, args).await?;

    let current = state.cloud.get_context(&slug).await.unwrap_or(json!({}));
    let mut known: Vec<Value> = current
        .get("known_issues")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    known.push(json!(format!("DECISION [{title}]: {decision}")));

    let patch = json!({"known_issues": known});
    let out = state.cloud.patch_context(&slug, &patch).await?;
    Ok(json!({"ok": true, "stub": "spec-2", "context": out}).to_string())
}

// TODO(spec-2): replace with POST /ideas.
async fn idea(state: &AppState, args: &Value) -> Result<String> {
    let text = arg_str_required(args, "text")?;
    let slug = resolve_slug(state, args).await?;

    let current = state.cloud.get_context(&slug).await.unwrap_or(json!({}));
    let mut open_q: Vec<Value> = current
        .get("open_questions")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    open_q.push(json!(format!("IDEA: {text}")));

    let patch = json!({"open_questions": open_q});
    let out = state.cloud.patch_context(&slug, &patch).await?;
    Ok(json!({"ok": true, "stub": "spec-2", "context": out}).to_string())
}

// TODO(spec-2): replace with POST /notes.
async fn note_append(state: &AppState, args: &Value) -> Result<String> {
    let markdown = arg_str_required(args, "markdown")?;
    let slug = resolve_slug(state, args).await?;

    // Append markdown to project.pitch (clamped to 2000 chars per backend constraint).
    let project = state.cloud.get_project(&slug).await?;
    let existing = project
        .get("pitch")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let joined = if existing.is_empty() {
        markdown.to_string()
    } else {
        format!("{existing}\n\n{markdown}")
    };
    let clamped: String = joined.chars().take(2000).collect();
    let patch = json!({"pitch": clamped});
    let out = state.cloud.patch_project(&slug, &patch).await?;
    Ok(json!({"ok": true, "stub": "spec-2", "project": out}).to_string())
}

async fn set_status(state: &AppState, args: &Value) -> Result<String> {
    let status = arg_str_required(args, "status")?;
    let slug = resolve_slug(state, args).await?;
    let out = state
        .cloud
        .patch_project(&slug, &json!({"status": status}))
        .await?;
    Ok(out.to_string())
}
