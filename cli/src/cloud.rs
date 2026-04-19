use anyhow::{bail, Context, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;

#[derive(Serialize)]
pub struct PairCompleteReq<'a> {
    pub device_code: &'a str,
}

#[derive(Deserialize, Debug)]
pub struct PairStartRes {
    pub device_code: String,
    pub user_code: String,
    #[allow(dead_code)]
    pub verification_url: String,
    pub expires_in: i64,
}

#[derive(Deserialize, Debug)]
pub struct PairCompleteRes {
    pub token: String,
    pub device_id: String,
    #[allow(dead_code)]
    pub user_id: String,
    #[allow(dead_code)]
    pub workspace_id: String,
    #[allow(dead_code)]
    pub workspace_slug: String,
}

#[derive(Deserialize, Debug)]
pub struct MeRes {
    pub user: UserBrief,
    pub active_workspace: WorkspaceBrief,
}

#[derive(Deserialize, Debug)]
pub struct UserBrief {
    pub email: String,
}

#[derive(Deserialize, Debug)]
pub struct WorkspaceBrief {
    pub slug: String,
    #[allow(dead_code)]
    pub name: String,
}

pub fn client() -> Result<Client> {
    Client::builder()
        .timeout(Duration::from_secs(30))
        .user_agent(concat!("hangar-cli/", env!("CARGO_PKG_VERSION")))
        .build()
        .context("building http client")
}

pub async fn pair_start(base_url: &str) -> Result<PairStartRes> {
    let client = client()?;
    let r = client
        .post(format!("{base_url}/api/v1/cli/pair/start"))
        .send()
        .await?;
    if !r.status().is_success() {
        bail!("pair start failed: {}", r.status());
    }
    Ok(r.json().await?)
}

pub async fn pair_complete(base_url: &str, device_code: &str) -> Result<Option<PairCompleteRes>> {
    let client = client()?;
    let r = client
        .post(format!("{base_url}/api/v1/cli/pair/complete"))
        .json(&PairCompleteReq { device_code })
        .send()
        .await?;
    if r.status() == reqwest::StatusCode::ACCEPTED {
        return Ok(None);
    }
    if !r.status().is_success() {
        bail!("pair complete failed: {}", r.status());
    }
    Ok(Some(r.json().await?))
}

pub async fn me(base_url: &str, token: &str) -> Result<MeRes> {
    let client = client()?;
    let r = client
        .get(format!("{base_url}/api/v1/me"))
        .bearer_auth(token)
        .send()
        .await?;
    if !r.status().is_success() {
        bail!("me failed: {}", r.status());
    }
    Ok(r.json().await?)
}

pub async fn revoke_device(base_url: &str, token: &str, device_id: &str) -> Result<()> {
    let client = client()?;
    let r = client
        .delete(format!("{base_url}/api/v1/cli/devices/{device_id}"))
        .bearer_auth(token)
        .send()
        .await?;
    if !r.status().is_success() {
        bail!("revoke failed: {}", r.status());
    }
    Ok(())
}
