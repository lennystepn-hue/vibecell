use anyhow::{Context, Result};
use std::time::Duration;
use tokio::time::sleep;

use crate::{cloud, config, keychain};

pub async fn run() -> Result<()> {
    let base_url = config::default_base_url();
    println!("-> starting pairing against {base_url}");

    let start = cloud::pair_start(&base_url)
        .await
        .context("starting pair")?;

    println!();
    println!("  Visit:     {}/cli/pair", base_url);
    println!("  Your code: {}", start.user_code);
    println!();

    // Best-effort open the browser for the user.
    let url = format!("{base_url}/cli/pair");
    let _ = open::that(&url);

    println!(
        "  Waiting for you to confirm in the browser (expires in {}s)...",
        start.expires_in
    );

    let mut delay = Duration::from_secs(2);
    let deadline = std::time::Instant::now() + Duration::from_secs(start.expires_in as u64);

    loop {
        sleep(delay).await;
        if std::time::Instant::now() > deadline {
            anyhow::bail!("pairing timed out; run `hangar pair` again");
        }
        match cloud::pair_complete(&base_url, &start.device_code).await? {
            None => {
                // Still pending — back off up to 5s.
                if delay < Duration::from_secs(5) {
                    delay =
                        std::cmp::min(Duration::from_secs(5), delay + Duration::from_millis(500));
                }
                continue;
            }
            Some(resp) => {
                // Try keychain first; fall back to config-file stash if unavailable
                // (headless Linux, no DBus, etc).
                let mut keychain_ok = true;
                let mut token_fallback: Option<String> = None;
                if let Err(e) = keychain::store_token(&base_url, &resp.device_id, &resp.token) {
                    tracing::warn!(
                        ?e,
                        "OS keychain unavailable; storing token in ~/.hangar/config.toml instead"
                    );
                    println!(
                        "  ! OS keychain unavailable ({e}); falling back to config-file token."
                    );
                    keychain_ok = false;
                    token_fallback = Some(resp.token.clone());
                }

                let me = cloud::me(&base_url, &resp.token).await?;
                let cfg = config::Config {
                    base_url: Some(base_url.clone()),
                    device_id: Some(resp.device_id),
                    workspace_slug: Some(me.active_workspace.slug.clone()),
                    user_email: Some(me.user.email.clone()),
                    bearer_token_fallback: token_fallback,
                };
                config::save(&cfg)?;

                println!();
                if keychain_ok {
                    println!(
                        "paired as {} in workspace {}",
                        me.user.email, me.active_workspace.slug
                    );
                } else {
                    println!(
                        "paired as {} in workspace {} (token stored in config file)",
                        me.user.email, me.active_workspace.slug
                    );
                }
                return Ok(());
            }
        }
    }
}
