//! Minimal types mirroring the backend project schema — just the fields we
//! stash in the SQLite cache. Everything else lives inside the `full_json`
//! blob and is deserialized lazily when Claude asks.

use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectListItem {
    pub id: String,
    pub slug: String,
    pub name: String,
    pub emoji: Option<String>,
    pub color: Option<String>,
    pub pitch: Option<String>,
    pub status: String,
    pub group_id: Option<String>,
    #[serde(default)]
    pub position: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectListPage {
    pub items: Vec<ProjectListItem>,
    #[serde(default)]
    pub next_cursor: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorkspaceBrief {
    pub id: String,
    pub slug: String,
    pub name: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct UserBrief {
    pub email: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MeResponse {
    pub user: UserBrief,
    pub active_workspace: WorkspaceBrief,
}

/// Row as we stage it into SQLite — `full_json` is the backend's
/// `ProjectFullOut` serialized as-is.
#[derive(Debug, Clone)]
pub struct ProjectSync {
    pub id: String,
    pub slug: String,
    pub name: String,
    pub emoji: Option<String>,
    pub pitch: Option<String>,
    pub status: String,
    pub group_id: Option<String>,
    pub position: i64,
    pub full_json: String,
    pub synced_at: String,
}

/// What we pull back out of SQLite for listing / dispatch.
#[derive(Debug, Clone)]
pub struct ProjectCacheRow {
    pub id: String,
    pub slug: String,
    pub name: String,
    pub emoji: Option<String>,
    pub pitch: Option<String>,
    pub status: String,
    pub group_id: Option<String>,
    pub position: i64,
    pub full_json: Option<String>,
}
