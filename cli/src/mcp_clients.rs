//! Detect installed MCP clients and wire Vibecell into each of them.
//!
//! This is what makes "automatic MCP installation" true. Before it, the
//! installer downloaded a binary and printed `next: run hangar pair` — it
//! touched no MCP configuration at all, and the user still had to work out
//! which of six editor tabs applied to them.
//!
//! Design constraints, learned the hard way from config files people care
//! about:
//!
//!   * **Additive.** A user's other MCP servers must survive untouched. We
//!     read, merge one key, write back.
//!   * **Idempotent.** Running twice is a no-op. An existing `vibecell` entry
//!     is replaced in place, not duplicated.
//!   * **Isolated.** One malformed config aborts that client only. Zed having
//!     a trailing comma in settings.json must not stop Cursor being wired up.
//!
//! The merge is a pure string→string function so every format can be tested
//! without touching a filesystem.

use anyhow::{Context, Result};
use serde_json::{json, Map, Value};
use std::path::{Path, PathBuf};

/// Which top-level key holds MCP servers, and how an entry is shaped.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfigFormat {
    /// `{"mcpServers": {"vibecell": {…}}}` — Claude Code, Cursor, Windsurf.
    /// Native remote HTTP transport.
    McpServersHttp,
    /// `{"mcpServers": {"vibecell": {"command": "npx", …}}}` — Claude Desktop.
    /// Desktop reads stdio servers from its config file, so remote HTTP goes
    /// through the `mcp-remote` bridge.
    McpServersBridge,
    /// `{"context_servers": {"vibecell": {"command": {…}}}}` — Zed.
    ContextServers,
}

#[derive(Debug, Clone)]
pub struct McpClient {
    /// Stable id reported to the onboarding stream.
    pub id: &'static str,
    /// Human label for the terminal output.
    pub label: &'static str,
    pub config_path: PathBuf,
    pub format: ConfigFormat,
}

/// Outcome for one client, mirrored into the `client.configured` event.
#[derive(Debug, Clone)]
pub struct Outcome {
    pub id: &'static str,
    pub ok: bool,
    pub reason: Option<String>,
}

fn home() -> Result<PathBuf> {
    dirs::home_dir().context("no home directory")
}

/// Claude Desktop keeps its config in the OS-conventional app-data location
/// rather than a dotfile, and the three differ enough to be worth spelling
/// out.
fn claude_desktop_config() -> Result<PathBuf> {
    let home = home()?;
    Ok(if cfg!(target_os = "macos") {
        home.join("Library/Application Support/Claude/claude_desktop_config.json")
    } else if cfg!(target_os = "windows") {
        dirs::config_dir()
            .context("no config directory")?
            .join("Claude/claude_desktop_config.json")
    } else {
        home.join(".config/Claude/claude_desktop_config.json")
    })
}

fn zed_settings() -> Result<PathBuf> {
    let home = home()?;
    Ok(if cfg!(target_os = "windows") {
        dirs::config_dir()
            .context("no config directory")?
            .join("Zed/settings.json")
    } else {
        home.join(".config/zed/settings.json")
    })
}

/// Every client we know how to configure, whether or not it is installed.
pub fn known_clients() -> Result<Vec<McpClient>> {
    let home = home()?;
    Ok(vec![
        McpClient {
            id: "claude-code",
            label: "Claude Code",
            config_path: home.join(".claude.json"),
            format: ConfigFormat::McpServersHttp,
        },
        McpClient {
            id: "claude-desktop",
            label: "Claude Desktop",
            config_path: claude_desktop_config()?,
            format: ConfigFormat::McpServersBridge,
        },
        McpClient {
            id: "cursor",
            label: "Cursor",
            config_path: home.join(".cursor/mcp.json"),
            format: ConfigFormat::McpServersHttp,
        },
        McpClient {
            id: "windsurf",
            label: "Windsurf",
            config_path: home.join(".codeium/windsurf/mcp_config.json"),
            format: ConfigFormat::McpServersHttp,
        },
        McpClient {
            id: "zed",
            label: "Zed",
            config_path: zed_settings()?,
            format: ConfigFormat::ContextServers,
        },
    ])
}

/// A client counts as present if its config file exists, or if its config
/// *directory* does.
///
/// The directory check matters: someone who installed Cursor yesterday and
/// never opened its MCP settings has `~/.cursor/` but no `mcp.json`. Writing
/// the file for them is the entire point of this command. Requiring the file
/// to exist first would skip exactly the users who need it most.
pub fn is_present(client: &McpClient) -> bool {
    if client.config_path.exists() {
        return true;
    }
    client
        .config_path
        .parent()
        .map(Path::exists)
        .unwrap_or(false)
}

/// The `vibecell` entry, shaped for one client's format.
fn entry_for(format: ConfigFormat, mcp_url: &str) -> Value {
    match format {
        ConfigFormat::McpServersHttp => json!({ "type": "http", "url": mcp_url }),
        ConfigFormat::McpServersBridge => json!({
            "command": "npx",
            "args": ["-y", "mcp-remote", mcp_url],
        }),
        ConfigFormat::ContextServers => json!({
            "command": { "path": "npx", "args": ["-y", "mcp-remote", mcp_url] },
        }),
    }
}

fn container_key(format: ConfigFormat) -> &'static str {
    match format {
        ConfigFormat::McpServersHttp | ConfigFormat::McpServersBridge => "mcpServers",
        ConfigFormat::ContextServers => "context_servers",
    }
}

/// Merge the Vibecell entry into an existing config document.
///
/// `existing` is the current file contents, or `None` when the file does not
/// exist yet. Returns the full document to write back.
///
/// Pure on purpose: every format and every edge case below is tested without
/// a filesystem, which is what makes it safe to point this at files people
/// would be upset to lose.
pub fn merge_config(existing: Option<&str>, format: ConfigFormat, mcp_url: &str) -> Result<String> {
    let mut root: Value = match existing {
        // An empty or whitespace-only file is a real thing — some installers
        // create it — and `serde_json` rejects it. Treat it as "no config".
        None => Value::Object(Map::new()),
        Some(raw) if raw.trim().is_empty() => Value::Object(Map::new()),
        Some(raw) => serde_json::from_str(raw).context("config file is not valid JSON")?,
    };

    if !root.is_object() {
        anyhow::bail!("config root is not a JSON object");
    }

    let key = container_key(format);
    let obj = root.as_object_mut().expect("checked above");
    let container = obj.entry(key).or_insert_with(|| Value::Object(Map::new()));

    if !container.is_object() {
        anyhow::bail!("`{key}` exists but is not a JSON object");
    }
    container
        .as_object_mut()
        .expect("checked above")
        // Replaces an existing entry rather than appending — this is what
        // makes a second run a no-op.
        .insert("vibecell".to_string(), entry_for(format, mcp_url));

    // Two-space indent matches what every one of these editors writes itself,
    // so re-running doesn't produce a noisy diff in someone's dotfiles repo.
    let mut out = serde_json::to_string_pretty(&root)?;
    out.push('\n');
    Ok(out)
}

/// Write the merged config for one client. Returns the outcome to report.
pub fn configure(client: &McpClient, mcp_url: &str) -> Outcome {
    let existing = match std::fs::read_to_string(&client.config_path) {
        Ok(raw) => Some(raw),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => None,
        Err(e) => {
            return Outcome {
                id: client.id,
                ok: false,
                reason: Some(format!("cannot read config: {e}")),
            }
        }
    };

    let merged = match merge_config(existing.as_deref(), client.format, mcp_url) {
        Ok(m) => m,
        Err(e) => {
            // Malformed config: report and move on. Rewriting a file we can't
            // parse would destroy settings we don't understand.
            return Outcome {
                id: client.id,
                ok: false,
                reason: Some(format!("{e}")),
            };
        }
    };

    if let Some(parent) = client.config_path.parent() {
        if let Err(e) = std::fs::create_dir_all(parent) {
            return Outcome {
                id: client.id,
                ok: false,
                reason: Some(format!("cannot create {}: {e}", parent.display())),
            };
        }
    }

    match std::fs::write(&client.config_path, merged) {
        Ok(()) => Outcome {
            id: client.id,
            ok: true,
            reason: None,
        },
        Err(e) => Outcome {
            id: client.id,
            ok: false,
            reason: Some(format!("cannot write config: {e}")),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const URL: &str = "https://vibecell.dev/mcp";

    fn parse(s: &str) -> Value {
        serde_json::from_str(s).expect("output must be valid JSON")
    }

    #[test]
    fn creates_the_container_when_the_file_does_not_exist() {
        let out = parse(&merge_config(None, ConfigFormat::McpServersHttp, URL).unwrap());
        assert_eq!(out["mcpServers"]["vibecell"]["url"], URL);
        assert_eq!(out["mcpServers"]["vibecell"]["type"], "http");
    }

    #[test]
    fn treats_an_empty_file_as_no_config() {
        // Some installers touch the file without writing anything, and
        // serde_json rejects "" — this used to be a crash.
        for raw in ["", "   ", "\n\n"] {
            let out = parse(&merge_config(Some(raw), ConfigFormat::McpServersHttp, URL).unwrap());
            assert_eq!(out["mcpServers"]["vibecell"]["url"], URL);
        }
    }

    #[test]
    fn preserves_other_mcp_servers() {
        let existing = r#"{"mcpServers":{"github":{"command":"gh-mcp"}}}"#;
        let out = parse(&merge_config(Some(existing), ConfigFormat::McpServersHttp, URL).unwrap());
        assert_eq!(out["mcpServers"]["github"]["command"], "gh-mcp");
        assert_eq!(out["mcpServers"]["vibecell"]["url"], URL);
    }

    #[test]
    fn preserves_unrelated_top_level_settings() {
        // Zed's settings.json is a whole editor config. Losing someone's
        // theme and keymap to an MCP install would be unforgivable.
        let existing = r#"{"theme":"One Dark","buffer_font_size":15}"#;
        let out = parse(&merge_config(Some(existing), ConfigFormat::ContextServers, URL).unwrap());
        assert_eq!(out["theme"], "One Dark");
        assert_eq!(out["buffer_font_size"], 15);
        assert_eq!(out["context_servers"]["vibecell"]["command"]["path"], "npx");
    }

    #[test]
    fn replaces_an_existing_vibecell_entry_rather_than_duplicating() {
        let first = merge_config(None, ConfigFormat::McpServersHttp, "https://old/mcp").unwrap();
        let second = merge_config(Some(&first), ConfigFormat::McpServersHttp, URL).unwrap();
        let out = parse(&second);
        assert_eq!(out["mcpServers"]["vibecell"]["url"], URL);
        assert_eq!(out["mcpServers"].as_object().unwrap().len(), 1);
    }

    #[test]
    fn running_twice_is_byte_identical() {
        let once = merge_config(None, ConfigFormat::McpServersHttp, URL).unwrap();
        let twice = merge_config(Some(&once), ConfigFormat::McpServersHttp, URL).unwrap();
        assert_eq!(once, twice, "a second run must be a no-op");
    }

    #[test]
    fn desktop_uses_the_stdio_bridge() {
        let out = parse(&merge_config(None, ConfigFormat::McpServersBridge, URL).unwrap());
        assert_eq!(out["mcpServers"]["vibecell"]["command"], "npx");
        assert_eq!(out["mcpServers"]["vibecell"]["args"][2], URL);
    }

    #[test]
    fn zed_uses_its_own_container_key() {
        let out = parse(&merge_config(None, ConfigFormat::ContextServers, URL).unwrap());
        assert!(out.get("mcpServers").is_none());
        assert_eq!(
            out["context_servers"]["vibecell"]["command"]["args"][2],
            URL
        );
    }

    #[test]
    fn refuses_malformed_json_instead_of_overwriting_it() {
        // The file has settings we cannot parse. Rewriting it would throw
        // away whatever the user had.
        let err = merge_config(Some("{ not json"), ConfigFormat::McpServersHttp, URL).unwrap_err();
        assert!(format!("{err}").contains("not valid JSON"));
    }

    #[test]
    fn refuses_when_the_container_key_holds_something_unexpected() {
        let existing = r#"{"mcpServers": ["a", "b"]}"#;
        let err = merge_config(Some(existing), ConfigFormat::McpServersHttp, URL).unwrap_err();
        assert!(format!("{err}").contains("not a JSON object"));
    }

    #[test]
    fn refuses_a_non_object_root() {
        let err = merge_config(Some("[1,2,3]"), ConfigFormat::McpServersHttp, URL).unwrap_err();
        assert!(format!("{err}").contains("root is not a JSON object"));
    }

    #[test]
    fn output_ends_with_a_newline() {
        // Dotfiles land in git repos; a missing trailing newline shows up as
        // "\ No newline at end of file" in every diff forever.
        let out = merge_config(None, ConfigFormat::McpServersHttp, URL).unwrap();
        assert!(out.ends_with('\n'));
    }

    #[test]
    fn every_known_client_has_a_distinct_id_and_path() {
        let clients = known_clients().unwrap();
        assert_eq!(clients.len(), 5);
        let mut ids: Vec<_> = clients.iter().map(|c| c.id).collect();
        ids.sort_unstable();
        ids.dedup();
        assert_eq!(ids.len(), 5, "client ids must be unique");

        let mut paths: Vec<_> = clients.iter().map(|c| c.config_path.clone()).collect();
        paths.sort();
        paths.dedup();
        assert_eq!(paths.len(), 5, "two clients must not share a config file");
    }
}
