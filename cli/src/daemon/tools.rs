//! MCP tool specs + dispatcher. 18 tools covering the core read/write surface
//! Claude Code needs to drive Vibecell during a coding session.
//!
//! Tool namespace is `vibecell.*` (user-visible). CLI binary stays `hangar`
//! (internal codename) to avoid breaking existing keychain/config paths.

use anyhow::{bail, Context, Result};
use serde_json::{json, Value};

use crate::daemon::mcp::AppState;

// ---------------------------------------------------------------------------
// Tool specs (served by GET /mcp/v1/tools/list)
// ---------------------------------------------------------------------------

pub fn tool_specs() -> Value {
    json!([
        {
            "name": "vibecell.ping",
            "description": "Health check. Returns ok=true + version + active project slug.",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "vibecell.active",
            "description": "Return the currently-active project's full aggregate (name, pitch, status, context, stack, links, commands, etc). Always call this at session start.",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        },
        {
            "name": "vibecell.list",
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
            "name": "vibecell.get",
            "description": "Return the full aggregate for a single project by slug.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"]
            }
        },
        {
            "name": "vibecell.brief",
            "description": "Generate a human-readable resurrection brief for a project (name, pitch, status, current focus, next step, suggested first move). Defaults to active project.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}}
            }
        },
        {
            "name": "vibecell.search",
            "description": "Federated full-text search across the workspace: projects, sessions, decisions, ideas, notes. Returns ranked hits with snippets.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "limit": {"type": "integer"}
                },
                "required": ["q"]
            }
        },
        {
            "name": "vibecell.recent_projects",
            "description": "Return up to n projects (default 5) ordered by sidebar position (proxy for recently-touched until sessions land).",
            "inputSchema": {
                "type": "object",
                "properties": {"n": {"type": "integer"}}
            }
        },
        {
            "name": "vibecell.switch",
            "description": "Switch the active project. Subsequent calls to vibecell.active / vibecell.brief default to this slug.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}},
                "required": ["slug"]
            }
        },
        {
            "name": "vibecell.log_session",
            "description": "Log a coding session: summary + optional files_touched + commits + next_step. Writes to the sessions table with source='skill'.",
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
            "name": "vibecell.update_context",
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
            "name": "vibecell.decision",
            "description": "Record an architectural decision (ADR-lite) on the active project: title, context, decision, consequences, reconsider_if.",
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
            "name": "vibecell.idea",
            "description": "Capture an idea. If `project` slug is supplied, files it against that project; otherwise goes to the workspace inbox.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "body": {"type": "string"},
                    "project": {"type": "string"}
                },
                "required": ["body"]
            }
        },
        {
            "name": "vibecell.note_append",
            "description": "Append a markdown block to the active project's notes, separated by a timestamped divider.",
            "inputSchema": {
                "type": "object",
                "properties": {"markdown": {"type": "string"}},
                "required": ["markdown"]
            }
        },
        {
            "name": "vibecell.ship",
            "description": "Record a ship event for the active project: version, summary, changelog_md (markdown). Auto-creates a lifecycle_event.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "version": {"type": "string"},
                    "summary": {"type": "string"},
                    "changelog_md": {"type": "string"}
                }
            }
        },
        {
            "name": "vibecell.status",
            "description": "Set the active project's status (idea | building | live | paused | shipped | archived | dead).",
            "inputSchema": {
                "type": "object",
                "properties": {"status": {"type": "string"}},
                "required": ["status"]
            }
        },
        {
            "name": "vibecell.run",
            "description": "Execute a saved project command. Resolves @label placeholders from the project's secret store (inline_encrypted via backend, op:// via 1Password CLI, bw:// via Bitwarden CLI). Returns exit code + last 4KB of stdout/stderr. 5-minute timeout.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "project": {"type": "string"}
                },
                "required": ["label"]
            }
        },
        {
            "name": "vibecell.claude_md",
            "description": "Generate a CLAUDE.md-ready markdown brief for a project: stack, infra, current state, links, commands. Pure read — no network besides the project fetch. Defaults to active project.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}}
            }
        },
        {
            "name": "vibecell.handover",
            "description": "Return a longer onboarding / resurrection brief as prose — what the project is, where it stands, what the user was about to do, suggested first move. Defaults to active project.",
            "inputSchema": {
                "type": "object",
                "properties": {"slug": {"type": "string"}}
            }
        }
    ])
}

// ---------------------------------------------------------------------------
// Dispatch
// ---------------------------------------------------------------------------

pub async fn dispatch(state: &AppState, name: &str, args: &Value) -> Result<String> {
    match name {
        "vibecell.ping" => ping(state).await,
        "vibecell.active" => active(state).await,
        "vibecell.list" => list(state, args).await,
        "vibecell.get" => get_project(state, args).await,
        "vibecell.brief" => brief(state, args).await,
        "vibecell.search" => search(state, args).await,
        "vibecell.recent_projects" => recent_projects(state, args).await,
        "vibecell.switch" => switch(state, args).await,
        "vibecell.log_session" => log_session(state, args).await,
        "vibecell.update_context" => update_context(state, args).await,
        "vibecell.decision" => decision(state, args).await,
        "vibecell.idea" => idea(state, args).await,
        "vibecell.note_append" => note_append(state, args).await,
        "vibecell.ship" => ship(state, args).await,
        "vibecell.status" => set_status(state, args).await,
        "vibecell.run" => run_tool(state, args).await,
        "vibecell.claude_md" => claude_md(state, args).await,
        "vibecell.handover" => handover(state, args).await,
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
/// we check the cache's `active_project` row (written by vibecell.switch).
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
    bail!("no active project — call vibecell.switch(slug) or `hangar sync` first")
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
        "Run vibecell.update_context to capture what you want to do next.".to_string()
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
    let limit = args.get("limit").and_then(|v| v.as_i64()).unwrap_or(50);
    let hits = state.cloud.search_all(q, limit).await?;
    Ok(json!({ "results": hits }).to_string())
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
    // Mirror into local cache so vibecell.active / vibecell.ping see the change.
    if let Ok(conn) = crate::cache::open() {
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

async fn log_session(state: &AppState, args: &Value) -> Result<String> {
    let summary = arg_str_required(args, "summary")?;
    let slug = resolve_slug(state, args).await?;
    let now = chrono::Utc::now().to_rfc3339();
    let body = json!({
        "started_at": now,
        "ended_at": now,
        "summary": summary,
        "next_step": arg_str(args, "next_step"),
        "files_touched": args.get("files_touched").cloned().unwrap_or(json!([])),
        "commits": args.get("commits").cloned().unwrap_or(json!([])),
        "source": "skill",
    });
    let out = state.cloud.create_session(&slug, &body).await?;
    Ok(out.to_string())
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

async fn decision(state: &AppState, args: &Value) -> Result<String> {
    let title = arg_str_required(args, "title")?;
    let decision = arg_str_required(args, "decision")?;
    let slug = resolve_slug(state, args).await?;
    let body = json!({
        "title": title,
        "decision": decision,
        "context": arg_str(args, "context"),
        "consequences": arg_str(args, "consequences"),
        "reconsider_if": arg_str(args, "reconsider_if"),
    });
    let out = state.cloud.create_decision(&slug, &body).await?;
    Ok(out.to_string())
}

async fn idea(state: &AppState, args: &Value) -> Result<String> {
    let body_text = arg_str_required(args, "body")?;
    let project = arg_str(args, "project");
    let payload = json!({
        "body": body_text,
        "source": "skill",
    });
    let out = if let Some(slug) = project {
        state.cloud.create_idea_project(slug, &payload).await?
    } else {
        state.cloud.create_idea_workspace(&payload).await?
    };
    Ok(out.to_string())
}

async fn note_append(state: &AppState, args: &Value) -> Result<String> {
    let markdown = arg_str_required(args, "markdown")?;
    let slug = resolve_slug(state, args).await?;
    let existing = state.cloud.get_notes(&slug).await.unwrap_or_default();
    let stamp = chrono::Utc::now().to_rfc3339();
    let appended = if existing.trim().is_empty() {
        format!("{stamp}\n{markdown}")
    } else {
        format!("{existing}\n\n---\n\n{stamp}\n{markdown}")
    };
    let out = state.cloud.put_notes(&slug, &appended).await?;
    Ok(out.to_string())
}

async fn ship(state: &AppState, args: &Value) -> Result<String> {
    let slug = resolve_slug(state, args).await?;
    let now = chrono::Utc::now().to_rfc3339();
    let body = json!({
        "shipped_at": now,
        "version": arg_str(args, "version"),
        "summary": arg_str(args, "summary"),
        "changelog_md": arg_str(args, "changelog_md"),
    });
    let out = state.cloud.create_ship(&slug, &body).await?;
    Ok(out.to_string())
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

// ---------------------------------------------------------------------------
// vibecell.run — piped output + secret resolution (Bundle 2)
// ---------------------------------------------------------------------------

async fn run_tool(state: &AppState, args: &Value) -> Result<String> {
    let label = arg_str_required(args, "label")?;
    let slug = resolve_slug(state, args).await?;
    let result = crate::cmd::run::run_capture(&state.cloud, &slug, label).await?;
    Ok(json!({
        "exit_code": result.exit_code,
        "stdout_tail": result.stdout_tail,
        "stderr_tail": result.stderr_tail,
        "duration_ms": result.duration_ms,
    })
    .to_string())
}

// ---------------------------------------------------------------------------
// vibecell.claude_md — generate CLAUDE.md for a project (HANGAR.md §15.1)
// ---------------------------------------------------------------------------

async fn claude_md(state: &AppState, args: &Value) -> Result<String> {
    let slug = resolve_slug(state, args).await?;
    let full = state.cloud.get_project(&slug).await?;
    Ok(render_claude_md(&full))
}

pub(crate) fn render_claude_md(full: &Value) -> String {
    let name = full
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or("Project");
    let pitch = full
        .get("pitch")
        .and_then(|v| v.as_str())
        .unwrap_or("(no pitch yet)");

    // Stack items — comma-sep, grouped informally.
    let stack: Vec<String> = full
        .get("stack")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|s| {
                    let n = s.get("name").and_then(|v| v.as_str()).unwrap_or("");
                    let k = s.get("kind").and_then(|v| v.as_str()).unwrap_or("");
                    if n.is_empty() {
                        None
                    } else if k.is_empty() {
                        Some(n.to_string())
                    } else {
                        Some(format!("{n} ({k})"))
                    }
                })
                .collect()
        })
        .unwrap_or_default();

    // Infra fields.
    let infra = full.get("infra").cloned().unwrap_or(json!({}));
    let infra_line = |field: &str| -> Option<String> {
        infra
            .get(field)
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(|s| s.to_string())
    };

    // Context.
    let ctx = full.get("context").cloned().unwrap_or(json!({}));
    let current_focus = ctx
        .get("current_focus")
        .and_then(|v| v.as_str())
        .unwrap_or("(unset)");
    let next_step = ctx
        .get("next_step")
        .and_then(|v| v.as_str())
        .unwrap_or("(unset)");
    let user_wants = ctx
        .get("user_wants")
        .and_then(|v| v.as_str())
        .unwrap_or("(unset)");
    let blocked_by = ctx
        .get("blocked_by")
        .and_then(|v| v.as_str())
        .unwrap_or("(none)");
    let open_questions: Vec<String> = ctx
        .get("open_questions")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();

    // Links.
    let links: Vec<String> = full
        .get("links")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|l| {
                    let kind = l.get("kind").and_then(|v| v.as_str()).unwrap_or("link");
                    let label = l.get("label").and_then(|v| v.as_str()).unwrap_or("");
                    let url = l.get("url").and_then(|v| v.as_str())?;
                    Some(format!(
                        "- [{kind}] {label_display} — {url}",
                        label_display = if label.is_empty() { kind } else { label },
                        kind = kind,
                        url = url
                    ))
                })
                .collect()
        })
        .unwrap_or_default();

    // Commands.
    let commands: Vec<String> = full
        .get("commands")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|c| {
                    let label = c.get("label").and_then(|v| v.as_str())?;
                    let cmd = c.get("command").and_then(|v| v.as_str())?;
                    Some(format!("- {label}: `{cmd}`"))
                })
                .collect()
        })
        .unwrap_or_default();

    // Assemble.
    let mut md = String::new();
    md.push_str(&format!("# {name}\n\n{pitch}\n\n"));

    md.push_str("## Stack\n");
    if stack.is_empty() {
        md.push_str("- (no stack items recorded)\n");
    } else {
        for item in &stack {
            md.push_str(&format!("- {item}\n"));
        }
    }
    md.push('\n');

    md.push_str("## Infra\n");
    let mut any_infra = false;
    for (field, label) in [
        ("server_alias", "Server"),
        ("domain_primary", "Domain"),
        ("db_host", "DB"),
        ("dns_provider", "DNS"),
    ] {
        if let Some(v) = infra_line(field) {
            md.push_str(&format!("- {label}: {v}\n"));
            any_infra = true;
        }
    }
    if !any_infra {
        md.push_str("- (no infra recorded)\n");
    }
    md.push_str("- Secrets: see `hangar secret list`\n\n");

    md.push_str("## Current state\n");
    md.push_str(&format!("- Focus: {current_focus}\n"));
    md.push_str(&format!("- Next: {next_step}\n"));
    md.push_str(&format!("- User wants: {user_wants}\n"));
    if open_questions.is_empty() {
        md.push_str("- Open questions: (none)\n");
    } else {
        md.push_str("- Open questions:\n");
        for q in &open_questions {
            md.push_str(&format!("  - {q}\n"));
        }
    }
    md.push_str(&format!("- Blocked by: {blocked_by}\n\n"));

    md.push_str("## Links\n");
    if links.is_empty() {
        md.push_str("- (no links recorded)\n");
    } else {
        for l in &links {
            md.push_str(&format!("{l}\n"));
        }
    }
    md.push('\n');

    md.push_str("## Commands\n");
    if commands.is_empty() {
        md.push_str("- (no commands saved — add one with `hangar set-command`)\n");
    } else {
        for c in &commands {
            md.push_str(&format!("{c}\n"));
        }
    }
    md.push('\n');

    md.push_str(&format!(
        "Generated by Vibecell {} on {}.\n",
        env!("CARGO_PKG_VERSION"),
        chrono::Utc::now().to_rfc3339()
    ));
    md
}

// ---------------------------------------------------------------------------
// vibecell.handover — prose onboarding brief (HANGAR.md §15.4)
// ---------------------------------------------------------------------------

async fn handover(state: &AppState, args: &Value) -> Result<String> {
    let slug = resolve_slug(state, args).await?;
    let full = state.cloud.get_project(&slug).await?;
    Ok(render_handover(&full))
}

pub(crate) fn render_handover(full: &Value) -> String {
    let name = full
        .get("name")
        .and_then(|v| v.as_str())
        .unwrap_or("the project");
    let pitch = full
        .get("pitch")
        .and_then(|v| v.as_str())
        .unwrap_or("(no pitch captured yet)");
    let status = full
        .get("status")
        .and_then(|v| v.as_str())
        .unwrap_or("idea");

    let ctx = full.get("context").cloned().unwrap_or(json!({}));
    let current_focus = ctx
        .get("current_focus")
        .and_then(|v| v.as_str())
        .unwrap_or("");
    let next_step = ctx.get("next_step").and_then(|v| v.as_str()).unwrap_or("");
    let user_wants = ctx.get("user_wants").and_then(|v| v.as_str()).unwrap_or("");
    let blocked_by = ctx.get("blocked_by").and_then(|v| v.as_str()).unwrap_or("");
    let open_q: Vec<String> = ctx
        .get("open_questions")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();
    let known_issues: Vec<String> = ctx
        .get("known_issues")
        .and_then(|v| v.as_array())
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect()
        })
        .unwrap_or_default();

    let commands_count = full
        .get("commands")
        .and_then(|v| v.as_array())
        .map(|a| a.len())
        .unwrap_or(0);

    // Compose prose. Target ~150-250 words.
    let mut p = String::new();
    p.push_str(&format!("{name} — {pitch}.\n\n"));

    // Where it stands.
    p.push_str(&format!("Status: **{status}**. "));
    if !current_focus.is_empty() {
        p.push_str(&format!("Current focus is *{current_focus}*. "));
    } else {
        p.push_str("No explicit focus is recorded. ");
    }
    if !user_wants.is_empty() {
        p.push_str(&format!("The user wants: {user_wants}. "));
    }
    p.push('\n');
    p.push('\n');

    // What broke / issues.
    if known_issues.is_empty() {
        p.push_str("No known issues logged. (Placeholder: SSL / commits / GitHub issues integrations will surface real breakage once Spec 3 Phase 5 lands.)\n\n");
    } else {
        p.push_str("Known issues:\n");
        for k in &known_issues {
            p.push_str(&format!("- {k}\n"));
        }
        p.push('\n');
    }

    // What user was about to do.
    if !next_step.is_empty() {
        p.push_str(&format!("**What you were about to do:** {next_step}. "));
    } else {
        p.push_str("**What you were about to do:** not recorded. ");
    }
    if !blocked_by.is_empty() && blocked_by != "(none)" {
        p.push_str(&format!("(Blocked by: {blocked_by}.) "));
    }
    p.push('\n');
    p.push('\n');

    // Open questions.
    if !open_q.is_empty() {
        p.push_str("Open questions:\n");
        for q in &open_q {
            p.push_str(&format!("- {q}\n"));
        }
        p.push('\n');
    }

    // Suggested first move.
    p.push_str("**Suggested first move:** ");
    let suggestion = if !next_step.is_empty() {
        format!("pick up where you left off — {next_step}")
    } else if !current_focus.is_empty() {
        format!("continue current focus ({current_focus})")
    } else if commands_count > 0 {
        "browse saved commands with `hangar run <label>` to recall what this project does, then call `vibecell.update_context` to set a focus before coding".to_string()
    } else {
        "call `vibecell.update_context` to set current_focus + next_step, then start a concrete task"
            .to_string()
    };
    p.push_str(&suggestion);
    p.push_str(".\n");
    p
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tool_specs_has_18_tools() {
        let specs = tool_specs();
        let arr = specs.as_array().expect("tool_specs is array");
        assert_eq!(arr.len(), 18, "expected 18 MCP tools");
        let names: Vec<&str> = arr
            .iter()
            .filter_map(|t| t.get("name").and_then(|v| v.as_str()))
            .collect();
        // Spec 2 new additions.
        assert!(names.contains(&"vibecell.ship"));
        // Existing write tools still present (no removals).
        for required in [
            "vibecell.log_session",
            "vibecell.decision",
            "vibecell.idea",
            "vibecell.note_append",
            "vibecell.search",
        ] {
            assert!(names.contains(&required), "missing {required}");
        }
    }

    #[test]
    fn claude_md_has_all_sections() {
        let full = json!({
            "name": "Hangar",
            "pitch": "Remember every project.",
            "status": "building",
            "context": {
                "current_focus": "bundle 2",
                "next_step": "ship MCP tools",
                "user_wants": "CLAUDE.md gen",
                "open_questions": ["what about sessions?"],
                "blocked_by": "(none)"
            },
            "stack": [{"name": "Rust", "kind": "lang"}],
            "infra": {"server_alias": "staging-vps", "domain_primary": "hangar.dev"},
            "links": [{"kind": "repo", "label": "GitHub", "url": "https://github.com/lenny/hangar"}],
            "commands": [{"label": "Deploy", "command": "make deploy"}]
        });
        let md = render_claude_md(&full);
        assert!(md.contains("# Hangar"));
        assert!(md.contains("## Stack"));
        assert!(md.contains("Rust (lang)"));
        assert!(md.contains("## Infra"));
        assert!(md.contains("staging-vps"));
        assert!(md.contains("hangar.dev"));
        assert!(md.contains("## Current state"));
        assert!(md.contains("bundle 2"));
        assert!(md.contains("## Links"));
        assert!(md.contains("[repo]"));
        assert!(md.contains("## Commands"));
        assert!(md.contains("`make deploy`"));
        assert!(md.contains("Generated by Vibecell"));
    }

    #[test]
    fn handover_prose_mentions_name_and_suggestion() {
        let full = json!({
            "name": "Widget",
            "pitch": "Count widgets.",
            "status": "live",
            "context": {
                "current_focus": "perf tuning",
                "next_step": "switch to sled",
                "user_wants": "faster search",
                "open_questions": [],
                "blocked_by": "(none)",
                "known_issues": []
            },
            "commands": []
        });
        let txt = render_handover(&full);
        assert!(txt.contains("Widget"));
        assert!(txt.contains("Count widgets"));
        assert!(txt.contains("Suggested first move"));
        assert!(txt.contains("switch to sled"));
    }
}
