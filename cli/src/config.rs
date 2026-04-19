use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Config {
    pub base_url: Option<String>,
    pub device_id: Option<String>,
    pub workspace_slug: Option<String>,
    pub user_email: Option<String>,
    /// Fallback when no OS keychain is available (headless Linux VPS etc).
    /// Never preferred when the keychain works.
    pub bearer_token_fallback: Option<String>,
}

pub fn config_dir() -> Result<PathBuf> {
    let home = dirs::home_dir().context("no home directory")?;
    Ok(home.join(".hangar"))
}

pub fn config_path() -> Result<PathBuf> {
    Ok(config_dir()?.join("config.toml"))
}

pub fn load() -> Result<Config> {
    let path = config_path()?;
    if !path.exists() {
        return Ok(Config::default());
    }
    let raw =
        std::fs::read_to_string(&path).with_context(|| format!("reading {}", path.display()))?;
    let cfg: Config = toml::from_str(&raw)?;
    Ok(cfg)
}

pub fn save(cfg: &Config) -> Result<()> {
    let dir = config_dir()?;
    std::fs::create_dir_all(&dir)?;
    let path = config_path()?;
    let raw = toml::to_string_pretty(cfg)?;
    std::fs::write(&path, raw)?;
    Ok(())
}

pub fn default_base_url() -> String {
    std::env::var("HANGAR_BASE_URL").unwrap_or_else(|_| "https://vibecell.dev".to_string())
}
