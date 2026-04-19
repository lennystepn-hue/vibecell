use anyhow::Result;

use crate::{cloud, config, keychain};

pub async fn run() -> Result<()> {
    let cfg = config::load()?;
    let base_url = cfg
        .base_url
        .clone()
        .unwrap_or_else(config::default_base_url);

    let Some(device_id) = cfg.device_id.as_deref() else {
        println!("not paired");
        return Ok(());
    };

    let token = keychain::load_token(&base_url, device_id)
        .ok()
        .or_else(|| cfg.bearer_token_fallback.clone());

    // Best-effort server revoke — OK if it fails, local cleanup is authoritative.
    if let Some(t) = token.as_deref() {
        if let Err(e) = cloud::revoke_device(&base_url, t, device_id).await {
            tracing::debug!(?e, "server revoke failed; proceeding with local cleanup");
        }
    }

    keychain::delete_token(&base_url, device_id).ok();
    let _ = std::fs::remove_file(config::config_path()?);
    println!("unpaired");
    Ok(())
}
