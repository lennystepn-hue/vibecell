//! `hangar daemon start` — foreground HTTP MCP server.

use anyhow::Result;
use clap::Subcommand;

#[derive(Subcommand)]
pub enum DaemonCommand {
    /// Start the HTTP MCP daemon in the foreground on 127.0.0.1:7421.
    Start,
}

pub async fn run(cmd: DaemonCommand) -> Result<()> {
    match cmd {
        DaemonCommand::Start => crate::daemon::start().await,
    }
}
