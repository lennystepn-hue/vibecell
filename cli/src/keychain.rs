//! Thin wrapper around the OS keychain.
//!
//! On headless Linux (no DBus / no secret-service) `keyring` returns
//! `NoStorageAccess` / `PlatformFailure`; callers fall back to the config-file
//! token stash so the CLI still works on a VPS test box.

use anyhow::{Context, Result};
use keyring::Entry;

const SERVICE: &str = "hangar.dev";

fn account_key(base_url: &str, device_id: &str) -> String {
    format!("{base_url}:{device_id}")
}

pub fn store_token(base_url: &str, device_id: &str, token: &str) -> Result<()> {
    let entry = Entry::new(SERVICE, &account_key(base_url, device_id))
        .context("creating keychain entry")?;
    entry.set_password(token).context("writing to keychain")?;
    Ok(())
}

pub fn load_token(base_url: &str, device_id: &str) -> Result<String> {
    let entry = Entry::new(SERVICE, &account_key(base_url, device_id))?;
    Ok(entry.get_password()?)
}

pub fn delete_token(base_url: &str, device_id: &str) -> Result<()> {
    let entry = Entry::new(SERVICE, &account_key(base_url, device_id))?;
    match entry.delete_credential() {
        Ok(()) => Ok(()),
        Err(keyring::Error::NoEntry) => Ok(()),
        Err(e) => Err(e.into()),
    }
}
