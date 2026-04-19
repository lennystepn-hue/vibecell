//! `hangar skill` — Claude skill installer. This bundle only ships `print`
//! (dumps SKILL.md from the configured backend). `install` lands in a later
//! bundle alongside the platform-service installer.

use anyhow::{Context, Result};
use clap::Subcommand;

use crate::config;

#[derive(Subcommand)]
pub enum SkillCommand {
    /// Fetch the Claude skill markdown from the backend and print to stdout.
    Print,
}

pub async fn run(cmd: SkillCommand) -> Result<()> {
    match cmd {
        SkillCommand::Print => print_skill().await,
    }
}

async fn print_skill() -> Result<()> {
    let base_url = config::load()
        .ok()
        .and_then(|c| c.base_url)
        .unwrap_or_else(config::default_base_url);
    let url = format!("{}/skill/SKILL.md", base_url.trim_end_matches('/'));
    let body = reqwest::get(&url)
        .await
        .with_context(|| format!("fetching {url}"))?
        .error_for_status()
        .with_context(|| format!("fetching {url}"))?
        .text()
        .await?;
    print!("{body}");
    Ok(())
}
