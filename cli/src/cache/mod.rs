//! SQLite-backed local cache of workspace + projects.
//!
//! Populated by `hangar sync`. Read by the MCP tools so they can answer
//! questions about "what projects do I have?" without a round-trip to the
//! cloud every time. Writes still go straight to the cloud — the cache is
//! only a read-through shortcut.

use anyhow::Result;
use rusqlite::{params, Connection, OptionalExtension};
use std::path::PathBuf;

use crate::config;

pub mod models;

pub use models::{ProjectCacheRow, ProjectSync};

const SCHEMA: &str = include_str!("schema.sql");

pub fn cache_path() -> Result<PathBuf> {
    Ok(config::config_dir()?.join("cache.sqlite"))
}

pub fn open() -> Result<Connection> {
    let dir = config::config_dir()?;
    std::fs::create_dir_all(&dir)?;
    let path = cache_path()?;
    let conn = Connection::open(&path)?;
    conn.execute_batch(SCHEMA)?;
    Ok(conn)
}

pub fn upsert_workspace(conn: &Connection, id: &str, slug: &str, name: &str) -> Result<()> {
    let synced_at = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO workspace(id, slug, name, synced_at) VALUES(?1,?2,?3,?4)\
         ON CONFLICT(id) DO UPDATE SET slug=excluded.slug, name=excluded.name, synced_at=excluded.synced_at",
        params![id, slug, name, synced_at],
    )?;
    Ok(())
}

pub fn upsert_project(conn: &Connection, p: &ProjectSync) -> Result<()> {
    conn.execute(
        "INSERT INTO projects(id, slug, name, emoji, pitch, status, group_id, position, full_json, synced_at) \
         VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9,?10) \
         ON CONFLICT(id) DO UPDATE SET \
           slug=excluded.slug, name=excluded.name, emoji=excluded.emoji, pitch=excluded.pitch, \
           status=excluded.status, group_id=excluded.group_id, position=excluded.position, \
           full_json=excluded.full_json, synced_at=excluded.synced_at",
        params![
            p.id,
            p.slug,
            p.name,
            p.emoji,
            p.pitch,
            p.status,
            p.group_id,
            p.position,
            p.full_json,
            p.synced_at
        ],
    )?;
    Ok(())
}

pub fn list_projects(conn: &Connection) -> Result<Vec<ProjectCacheRow>> {
    let mut stmt = conn.prepare(
        "SELECT id, slug, name, emoji, pitch, status, group_id, position, full_json \
         FROM projects ORDER BY position ASC, name ASC",
    )?;
    let rows = stmt.query_map([], |r| {
        Ok(ProjectCacheRow {
            id: r.get(0)?,
            slug: r.get(1)?,
            name: r.get(2)?,
            emoji: r.get(3)?,
            pitch: r.get(4)?,
            status: r.get(5)?,
            group_id: r.get(6)?,
            position: r.get(7)?,
            full_json: r.get(8)?,
        })
    })?;
    rows.collect::<Result<Vec<_>, _>>().map_err(Into::into)
}

pub fn get_project_full_json(conn: &Connection, slug: &str) -> Result<Option<String>> {
    let v: Option<Option<String>> = conn
        .query_row(
            "SELECT full_json FROM projects WHERE slug = ?1",
            params![slug],
            |r| r.get::<_, Option<String>>(0),
        )
        .optional()?;
    Ok(v.flatten())
}

pub fn set_active_project(conn: &Connection, workspace_id: &str, slug: &str) -> Result<()> {
    let set_at = chrono::Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO active_project(workspace_id, project_slug, set_at) VALUES(?1,?2,?3) \
         ON CONFLICT(workspace_id) DO UPDATE SET project_slug=excluded.project_slug, set_at=excluded.set_at",
        params![workspace_id, slug, set_at],
    )?;
    Ok(())
}

pub fn get_active_slug(conn: &Connection) -> Result<Option<String>> {
    Ok(conn
        .query_row("SELECT project_slug FROM active_project LIMIT 1", [], |r| {
            r.get::<_, String>(0)
        })
        .optional()?)
}

pub fn clear_projects_not_in(conn: &Connection, keep_ids: &[String]) -> Result<()> {
    if keep_ids.is_empty() {
        conn.execute("DELETE FROM projects", [])?;
        return Ok(());
    }
    // rusqlite does not bind slices directly; build a placeholder list.
    let placeholders: Vec<String> = (1..=keep_ids.len()).map(|i| format!("?{i}")).collect();
    let sql = format!(
        "DELETE FROM projects WHERE id NOT IN ({})",
        placeholders.join(",")
    );
    let params_vec: Vec<&dyn rusqlite::ToSql> =
        keep_ids.iter().map(|s| s as &dyn rusqlite::ToSql).collect();
    conn.execute(&sql, params_vec.as_slice())?;
    Ok(())
}
