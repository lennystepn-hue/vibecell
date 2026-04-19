//! `hangar sync` — pull workspace + projects from cloud into SQLite cache.

use anyhow::{Context, Result};

use crate::{cache, cloud, config, keychain};

pub async fn run() -> Result<()> {
    let cfg = config::load()?;
    let base_url = cfg
        .base_url
        .clone()
        .unwrap_or_else(config::default_base_url);

    let device_id = cfg
        .device_id
        .as_deref()
        .context("not paired — run `hangar pair` first")?;

    let token = keychain::load_token(&base_url, device_id)
        .ok()
        .or_else(|| cfg.bearer_token_fallback.clone())
        .context("no bearer token — run `hangar pair` again")?;

    println!("-> syncing from {base_url}");

    let client = cloud::Client::new(base_url.clone(), token.clone())?;

    // 1. /api/v1/me — workspace identity
    let me: serde_json::Value = client.me().await?;
    let ws = me
        .get("active_workspace")
        .context("me response missing active_workspace")?;
    let ws_id = ws
        .get("id")
        .and_then(|v| v.as_str())
        .context("active_workspace.id missing")?;
    let ws_slug = ws.get("slug").and_then(|v| v.as_str()).unwrap_or("default");
    let ws_name = ws.get("name").and_then(|v| v.as_str()).unwrap_or(ws_slug);
    let user_email = me
        .get("user")
        .and_then(|u| u.get("email"))
        .and_then(|v| v.as_str())
        .unwrap_or("<unknown>");
    println!("  workspace: {user_email} / {ws_slug}");

    // 2. /api/v1/projects?limit=200 — list
    let page = client
        .list_projects(None, None, None, Some(200))
        .await
        .context("listing projects")?;
    let items = page
        .get("items")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    // 3. for each project, fetch /api/v1/projects/:slug full aggregate
    let conn = cache::open()?;
    cache::upsert_workspace(&conn, ws_id, ws_slug, ws_name)?;

    let mut kept_ids: Vec<String> = Vec::with_capacity(items.len());
    let now = chrono::Utc::now().to_rfc3339();
    let mut count = 0usize;

    for item in &items {
        let slug = item
            .get("slug")
            .and_then(|v| v.as_str())
            .unwrap_or_default();
        if slug.is_empty() {
            continue;
        }

        let full = match client.get_project(slug).await {
            Ok(f) => f,
            Err(e) => {
                tracing::warn!(%slug, ?e, "skipping project (fetch failed)");
                continue;
            }
        };

        let id = full
            .get("id")
            .and_then(|v| v.as_str())
            .unwrap_or_default()
            .to_string();
        if id.is_empty() {
            continue;
        }
        kept_ids.push(id.clone());

        let sync_row = cache::ProjectSync {
            id,
            slug: full
                .get("slug")
                .and_then(|v| v.as_str())
                .unwrap_or(slug)
                .to_string(),
            name: full
                .get("name")
                .and_then(|v| v.as_str())
                .unwrap_or(slug)
                .to_string(),
            emoji: full
                .get("emoji")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            pitch: full
                .get("pitch")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            status: full
                .get("status")
                .and_then(|v| v.as_str())
                .unwrap_or("idea")
                .to_string(),
            group_id: full
                .get("group_id")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            position: full.get("position").and_then(|v| v.as_i64()).unwrap_or(0),
            full_json: full.to_string(),
            synced_at: now.clone(),
        };
        cache::upsert_project(&conn, &sync_row)?;
        count += 1;
    }

    // Remove stale rows that no longer exist remotely.
    cache::clear_projects_not_in(&conn, &kept_ids)?;

    println!(
        "  pulled {count} project{}",
        if count == 1 { "" } else { "s" }
    );
    let path = cache::cache_path()?;
    println!("ok cache up to date ({})", path.display());
    Ok(())
}
