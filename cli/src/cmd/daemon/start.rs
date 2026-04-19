//! `hangar daemon start` — delegate to the crate-level daemon runtime.

use anyhow::Result;

pub async fn run() -> Result<()> {
    crate::daemon::start().await
}
