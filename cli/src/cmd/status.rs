use anyhow::Result;

use crate::{cloud, config, keychain};

pub async fn run() -> Result<()> {
    let cfg = config::load()?;
    let base_url = cfg
        .base_url
        .clone()
        .unwrap_or_else(config::default_base_url);

    let Some(device_id) = cfg.device_id.as_deref() else {
        println!("not paired - run `hangar pair` to connect this device");
        return Ok(());
    };

    // Try keychain first, then the config-file fallback.
    let token = keychain::load_token(&base_url, device_id)
        .ok()
        .or_else(|| cfg.bearer_token_fallback.clone());

    let Some(token) = token else {
        let email = cfg.user_email.as_deref().unwrap_or("<unknown>");
        println!(
            "config says paired as {email} (device {device_id}) but no token in keychain - run `hangar pair` again"
        );
        return Ok(());
    };

    match cloud::me(&base_url, &token).await {
        Ok(me) => {
            println!(
                "paired as {} in workspace {} (device {device_id})",
                me.user.email, me.active_workspace.slug
            );
        }
        Err(_) => {
            let email = cfg.user_email.as_deref().unwrap_or("<unknown>");
            let ws = cfg.workspace_slug.as_deref().unwrap_or("<unknown>");
            println!(
                "paired as {email} / {ws} (device {device_id}), but server rejected token - try `hangar unpair` + `hangar pair`"
            );
        }
    }
    Ok(())
}
