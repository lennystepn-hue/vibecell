use clap::{Parser, Subcommand};

mod cache;
mod cloud;
mod cmd;
mod config;
mod daemon;
mod keychain;

#[derive(Parser)]
#[command(name = "hangar", version, about = "Hangar CLI + daemon + MCP server", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Command>,
}

#[derive(Subcommand)]
enum Command {
    /// Pair this device with a Hangar workspace via the device-code flow.
    Pair,
    /// Show current pairing status.
    Status,
    /// Revoke the current pairing (removes keychain entry + server-side device).
    Unpair,
    /// Pull workspace + projects into the local SQLite cache.
    Sync,
    /// Run the HTTP MCP daemon (127.0.0.1:7421).
    Daemon {
        #[command(subcommand)]
        cmd: cmd::daemon::DaemonCommand,
    },
    /// Print (or rotate) the MCP bearer token used by Claude Code.
    #[command(name = "mcp-token")]
    McpToken(cmd::mcp_token::McpTokenArgs),
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "hangar=info".into()),
        )
        .without_time()
        .init();

    let cli = Cli::parse();
    match cli.command {
        Some(Command::Pair) => cmd::pair::run().await,
        Some(Command::Status) => cmd::status::run().await,
        Some(Command::Unpair) => cmd::unpair::run().await,
        Some(Command::Sync) => cmd::sync::run().await,
        Some(Command::Daemon { cmd }) => cmd::daemon::run(cmd).await,
        Some(Command::McpToken(args)) => cmd::mcp_token::run(args).await,
        None => {
            println!(
                "hangar {} — subcommands: pair | status | unpair | sync | daemon | mcp-token",
                env!("CARGO_PKG_VERSION")
            );
            println!("run `hangar pair` to connect this device.");
            Ok(())
        }
    }
}
