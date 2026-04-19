use clap::{Parser, Subcommand};

mod cache;
mod cloud;
mod cmd;
mod config;
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
        None => {
            println!(
                "hangar {} — subcommands: pair | status | unpair | sync",
                env!("CARGO_PKG_VERSION")
            );
            println!("run `hangar pair` to connect this device.");
            Ok(())
        }
    }
}
