CREATE TABLE IF NOT EXISTS workspace (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  synced_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  emoji TEXT,
  pitch TEXT,
  status TEXT NOT NULL,
  group_id TEXT,
  position INTEGER NOT NULL DEFAULT 0,
  full_json TEXT,
  synced_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_projects_slug ON projects(slug);

CREATE TABLE IF NOT EXISTS active_project (
  workspace_id TEXT PRIMARY KEY,
  project_slug TEXT NOT NULL,
  set_at TEXT NOT NULL
);
