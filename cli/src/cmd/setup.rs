//! `hangar setup --code <CODE>` — the whole install, in one command.
//!
//! This is what the one-liner from `/i/<code>` ends up running. It replaces
//! the old "download the binary, now go read a settings page" ending with:
//! pair this device, wire up every MCP client on the machine, install the
//! skill, and report each step to the browser so the user watches it happen.
//!
//! Failure policy is deliberate and not uniform:
//!
//!   * Redeeming the code is fatal. Without a token nothing else can work,
//!     and the message has to say *why* (expired vs already used) because
//!     that determines what the user does next.
//!   * Everything after it is best-effort and reported. A machine with Zed
//!     but no Cursor is normal, not an error, and one editor's broken config
//!     must not cost the user the other four.

use anyhow::{Context, Result};
use clap::Args;

use crate::{cloud, cmd::skill, config, keychain, mcp_clients};

#[derive(Args, Debug)]
pub struct SetupArgs {
    /// One-time setup code from the dashboard. Also read from
    /// HANGAR_SETUP_CODE, which is how the `/i/<code>` one-liner passes it.
    #[arg(long)]
    pub code: Option<String>,
}

/// Local hostname, so the device list in Settings says something a human can
/// recognise rather than a bare ULID.
fn device_name() -> Option<String> {
    std::env::var("COMPUTERNAME")
        .or_else(|_| std::env::var("HOSTNAME"))
        .ok()
        .filter(|s| !s.trim().is_empty())
}

pub async fn run(args: SetupArgs) -> Result<()> {
    let code = args
        .code
        .or_else(|| std::env::var("HANGAR_SETUP_CODE").ok())
        .filter(|c| !c.trim().is_empty())
        .context(
            "no setup code — pass --code <CODE>, or use the one-line command from the dashboard",
        )?;

    let base_url = config::default_base_url();
    let mcp_url = format!("{}/mcp", base_url.trim_end_matches('/'));

    // ── 1. Redeem ───────────────────────────────────────────────────────
    println!("-> pairing this device");
    let paired = cloud::redeem_code(&base_url, code.trim(), device_name().as_deref()).await?;

    // Keychain first, config-file fallback — same policy as `hangar pair`,
    // because headless Linux boxes have no keychain and refusing to install
    // there would be worse than a slightly less protected token.
    let mut token_fallback = None;
    if let Err(e) = keychain::store_token(&base_url, &paired.device_id, &paired.token) {
        tracing::warn!(?e, "OS keychain unavailable; storing token in config file");
        println!("   ! OS keychain unavailable ({e}); using config-file token");
        token_fallback = Some(paired.token.clone());
    }

    let me = cloud::me(&base_url, &paired.token).await?;
    config::save(&config::Config {
        base_url: Some(base_url.clone()),
        device_id: Some(paired.device_id.clone()),
        workspace_slug: Some(me.active_workspace.slug.clone()),
        user_email: Some(me.user.email.clone()),
        bearer_token_fallback: token_fallback,
    })?;
    println!("   paired as {}", me.user.email);

    cloud::report_onboarding(&base_url, &paired.token, "paired", None, None, None).await;

    // ── 2. MCP clients ──────────────────────────────────────────────────
    println!();
    println!("-> configuring MCP clients");

    let clients = mcp_clients::known_clients()?;
    let mut configured = 0usize;

    for client in &clients {
        if !mcp_clients::is_present(client) {
            println!("   ○ {:<16} not found", client.label);
            continue;
        }
        let outcome = mcp_clients::configure(client, &mcp_url);
        if outcome.ok {
            configured += 1;
            println!("   ✓ {:<16} {}", client.label, client.config_path.display());
        } else {
            println!(
                "   ✗ {:<16} {}",
                client.label,
                outcome.reason.as_deref().unwrap_or("failed")
            );
        }
        cloud::report_onboarding(
            &base_url,
            &paired.token,
            "client.configured",
            Some(outcome.id),
            Some(outcome.ok),
            outcome.reason.as_deref(),
        )
        .await;
    }

    // ── 3. Skill ────────────────────────────────────────────────────────
    println!();
    let status = skill::ensure_installed_quietly().await;
    println!("-> {status}");

    // ── 4. What now ─────────────────────────────────────────────────────
    println!();
    if configured == 0 {
        // Not a failure: plenty of people pair a server before installing an
        // editor on it. But saying "done" here would be a lie.
        println!("No MCP clients found on this machine yet.");
        println!("Install one and re-run `hangar setup` — or point your editor at {mcp_url}");
    } else {
        println!(
            "Done — {configured} client{} wired up.",
            if configured == 1 { "" } else { "s" }
        );
        println!("Open your editor and ask it what you're working on.");
    }

    Ok(())
}
