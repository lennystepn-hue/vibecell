//! Minimal types mirroring the backend project schema — just the fields we
//! stash in the SQLite cache. Everything else lives inside the `full_json`
//! blob and is deserialized lazily when Claude asks.

use serde::{Deserialize, Serialize};

/// Row as we stage it into SQLite — `full_json` is the backend's
/// `ProjectFullOut` serialized as-is.
#[derive(Debug, Clone, Serialize, Deserialize)]
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
#[allow(dead_code)]
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
