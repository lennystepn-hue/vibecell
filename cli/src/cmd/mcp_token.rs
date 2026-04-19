//! `hangar mcp-token [--rotate]` — print (or regenerate) the MCP bearer.

use anyhow::Result;
use clap::Args;

use crate::daemon;

#[derive(Args)]
pub struct McpTokenArgs {
    /// Generate a new token, overwrite the token file, and print it.
    /// Note: a running daemon will keep serving the OLD token until restarted.
    #[arg(long)]
    pub rotate: bool,
}

pub async fn run(args: McpTokenArgs) -> Result<()> {
    if args.rotate {
        let tok = daemon::generate_token();
        daemon::write_token(&tok)?;
        println!("Bearer {tok}");
        println!("(note: restart `hangar daemon start` to pick up the new token)");
        return Ok(());
    }

    match daemon::read_token() {
        Ok(tok) => {
            println!("Bearer {tok}");
            Ok(())
        }
        Err(_) => {
            println!("no token yet — run `hangar daemon start` first");
            Ok(())
        }
    }
}
