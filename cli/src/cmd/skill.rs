//! `hangar skill` — Claude skill manager.
//!
//! `print`   — fetch SKILL.md from the backend and dump to stdout (unchanged).
//! `install` — copy SKILL.md into `~/.claude/skills/vibecell/SKILL.md` so Claude
//!             auto-loads Vibecell context on every session.
//! `update`  — refresh an installed skill if the remote content changed.

use anyhow::{bail, Context, Result};
use clap::Subcommand;
use std::path::PathBuf;

use crate::config;

#[derive(Subcommand)]
pub enum SkillCommand {
    /// Fetch the Claude skill markdown from the backend and print to stdout.
    Print,
    /// Install SKILL.md into `~/.claude/skills/vibecell/SKILL.md`.
    Install {
        /// Overwrite an existing skill file that differs from the remote copy.
        #[arg(long)]
        force: bool,
    },
    /// Refresh an already-installed skill from the backend.
    Update,
}

pub async fn run(cmd: SkillCommand) -> Result<()> {
    match cmd {
        SkillCommand::Print => print_skill().await,
        SkillCommand::Install { force } => install_skill(force).await,
        SkillCommand::Update => update_skill().await,
    }
}

fn base_url() -> String {
    config::load()
        .ok()
        .and_then(|c| c.base_url)
        .unwrap_or_else(config::default_base_url)
}

pub(crate) fn claude_skill_path() -> Result<PathBuf> {
    let home = dirs::home_dir().context("no home directory")?;
    Ok(home
        .join(".claude")
        .join("skills")
        .join("vibecell")
        .join("SKILL.md"))
}

pub(crate) async fn fetch_skill(base_url: &str) -> Result<String> {
    let url = format!("{}/skill/SKILL.md", base_url.trim_end_matches('/'));
    let resp = reqwest::get(&url)
        .await
        .with_context(|| format!("fetching {url}"))?;
    if !resp.status().is_success() {
        bail!("fetch skill failed: {} from {}", resp.status(), url);
    }
    let body = resp.text().await?;
    Ok(body)
}

async fn print_skill() -> Result<()> {
    let body = fetch_skill(&base_url()).await?;
    print!("{body}");
    Ok(())
}

/// Install or refresh the SKILL.md without producing user-facing prompts.
/// Used by `hangar pair` to auto-install on first connect. Returns a short
/// status line ("installed", "up-to-date", "updated <delta>") that the
/// caller can print however they like. Never fails the parent flow — any
/// error is downgraded to a soft warning.
pub(crate) async fn ensure_installed_quietly() -> String {
    let remote = match fetch_skill(&base_url()).await {
        Ok(s) => s,
        Err(e) => {
            return format!("warn: SKILL fetch failed ({e}) — run `hangar skill install` manually")
        }
    };
    let dest = match claude_skill_path() {
        Ok(p) => p,
        Err(e) => return format!("warn: no home dir ({e}) — skipping SKILL install"),
    };
    if dest.exists() {
        match std::fs::read_to_string(&dest) {
            Ok(existing) if existing == remote => "SKILL.md up-to-date".to_string(),
            Ok(existing) => {
                if let Some(parent) = dest.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                if let Err(e) = std::fs::write(&dest, &remote) {
                    return format!("warn: SKILL update failed ({e})");
                }
                let delta = remote.len() as i64 - existing.len() as i64;
                format!("SKILL.md updated ({delta:+} bytes)")
            }
            Err(e) => format!("warn: read existing SKILL failed ({e})"),
        }
    } else {
        if let Some(parent) = dest.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Err(e) = std::fs::write(&dest, &remote) {
            return format!("warn: SKILL install failed ({e})");
        }
        format!("SKILL.md installed at {}", dest.display())
    }
}

async fn install_skill(force: bool) -> Result<()> {
    let remote = fetch_skill(&base_url()).await?;
    let dest = claude_skill_path()?;
    if dest.exists() && !force {
        let existing = std::fs::read_to_string(&dest)
            .with_context(|| format!("reading existing skill at {}", dest.display()))?;
        if existing == remote {
            println!(
                "i skill already installed at {} (no changes)",
                dest.display()
            );
            return Ok(());
        }
        bail!(
            "skill file already exists at {} — pass --force to overwrite",
            dest.display()
        );
    }
    if let Some(parent) = dest.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("creating {}", parent.display()))?;
    }
    std::fs::write(&dest, &remote).with_context(|| format!("writing {}", dest.display()))?;
    println!("ok installed skill to {}", dest.display());
    println!("  Claude will now auto-load Vibecell context on session start.");
    Ok(())
}

async fn update_skill() -> Result<()> {
    let remote = fetch_skill(&base_url()).await?;
    let dest = claude_skill_path()?;
    if !dest.exists() {
        println!("i skill not installed — run `hangar skill install` first");
        return Ok(());
    }
    let existing = std::fs::read_to_string(&dest)
        .with_context(|| format!("reading existing skill at {}", dest.display()))?;
    if existing == remote {
        println!("ok skill up to date (no changes)");
        return Ok(());
    }
    std::fs::write(&dest, &remote).with_context(|| format!("writing {}", dest.display()))?;
    let delta = remote.len() as i64 - existing.len() as i64;
    println!("ok updated skill at {} ({:+} bytes)", dest.display(), delta);
    Ok(())
}
