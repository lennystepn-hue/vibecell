//! Daemon — runs the HTTP MCP server on 127.0.0.1:7421 so Claude Code can
//! drive Hangar via bearer-authenticated HTTP JSON calls.

use anyhow::{Context, Result};
use rand::RngCore;
use std::path::PathBuf;

use crate::{cloud, config, keychain};

pub mod mcp;
pub mod tools;

pub fn token_file_path() -> Result<PathBuf> {
    Ok(config::config_dir()?.join("mcp-token"))
}

pub fn generate_token() -> String {
    let mut buf = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut buf);
    // URL-safe base64 without padding — short, copy-pasteable, no shell quoting.
    use base64::engine::general_purpose::URL_SAFE_NO_PAD;
    use base64::Engine as _;
    URL_SAFE_NO_PAD.encode(buf)
}

pub fn write_token(token: &str) -> Result<()> {
    let dir = config::config_dir()?;
    std::fs::create_dir_all(&dir)?;
    let path = token_file_path()?;
    std::fs::write(&path, token)?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mut perms = std::fs::metadata(&path)?.permissions();
        perms.set_mode(0o600);
        std::fs::set_permissions(&path, perms)?;
    }
    Ok(())
}

pub fn read_token() -> Result<String> {
    let path = token_file_path()?;
    let tok =
        std::fs::read_to_string(&path).with_context(|| format!("reading {}", path.display()))?;
    Ok(tok.trim().to_string())
}

/// Load the device bearer from keychain first, falling back to the config-file
/// stash (headless Linux VPS, no DBus).
pub fn load_device_bearer() -> Result<(String, String)> {
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
        .context("no device bearer — run `hangar pair` again")?;
    Ok((base_url, token))
}

pub async fn start() -> Result<()> {
    let (base_url, device_bearer) = load_device_bearer()?;

    // Mint + persist a fresh MCP bearer for this daemon session.
    let mcp_token = generate_token();
    write_token(&mcp_token)?;

    let cloud_client = cloud::Client::new(base_url, device_bearer)?;

    let state = std::sync::Arc::new(mcp::AppState {
        token: mcp_token.clone(),
        cloud: cloud_client,
    });

    let token_path = token_file_path()?;
    println!("ok daemon started on http://127.0.0.1:7421");
    println!("  MCP bearer: {mcp_token}");
    println!("  token file: {}", token_path.display());
    println!("  Ctrl+C to stop");

    mcp::serve(state).await
}
