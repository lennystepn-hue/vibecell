//! `hangar daemon` — foreground start + platform-service installer.
//!
//! Subcommands:
//!   start      — run the HTTP MCP server in the foreground (Bundle 1).
//!   install    — register a launchd / systemd --user / Task Scheduler entry
//!                so the daemon auto-starts on login.
//!   uninstall  — reverse the above.
//!   status     — best-effort: check TCP 127.0.0.1:7421 + detect PID.
//!   stop       — SIGTERM / taskkill the running daemon.

use anyhow::Result;
use clap::Subcommand;

pub mod install;
pub mod start;
pub mod status;
pub mod stop;
pub mod uninstall;

#[derive(Subcommand)]
pub enum DaemonCommand {
    /// Start the HTTP MCP daemon in the foreground on 127.0.0.1:7421.
    Start,
    /// Register the daemon as an auto-starting platform service.
    Install,
    /// Remove the platform-service registration.
    Uninstall,
    /// Report whether the daemon is reachable on 127.0.0.1:7421 (+ PID).
    Status,
    /// Stop the running daemon.
    Stop,
}

pub async fn run(cmd: DaemonCommand) -> Result<()> {
    match cmd {
        DaemonCommand::Start => start::run().await,
        DaemonCommand::Install => install::run().await,
        DaemonCommand::Uninstall => uninstall::run().await,
        DaemonCommand::Status => status::run().await,
        DaemonCommand::Stop => stop::run().await,
    }
}
