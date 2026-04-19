use anyhow::{bail, Context, Result};
use reqwest::Client as HttpClient;
use serde::{Deserialize, Serialize};
use serde_json::Value;
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
    #[allow(dead_code)]
    pub id: String,
    pub slug: String,
    #[allow(dead_code)]
    pub name: String,
}

pub fn client() -> Result<HttpClient> {
    HttpClient::builder()
        .timeout(Duration::from_secs(30))
        .user_agent(concat!("hangar-cli/", env!("CARGO_PKG_VERSION")))
        .build()
        .context("building http client")
}

pub async fn pair_start(base_url: &str) -> Result<PairStartRes> {
    let c = client()?;
    let r = c
        .post(format!("{base_url}/api/v1/cli/pair/start"))
        .send()
        .await?;
    if !r.status().is_success() {
        bail!("pair start failed: {}", r.status());
    }
    Ok(r.json().await?)
}

pub async fn pair_complete(base_url: &str, device_code: &str) -> Result<Option<PairCompleteRes>> {
    let c = client()?;
    let r = c
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
    let c = client()?;
    let r = c
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
    let c = client()?;
    let r = c
        .delete(format!("{base_url}/api/v1/cli/devices/{device_id}"))
        .bearer_auth(token)
        .send()
        .await?;
    if !r.status().is_success() {
        bail!("revoke failed: {}", r.status());
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// `Client` — a reusable bearer+base_url wrapper for the daemon/MCP tools so we
// don't repeat reqwest boilerplate. Methods intentionally return `Value` where
// possible so tool handlers can pass JSON straight through to Claude.
// ---------------------------------------------------------------------------

#[derive(Clone)]
pub struct Client {
    pub base_url: String,
    pub token: String,
    http: HttpClient,
}

impl Client {
    pub fn new(base_url: String, token: String) -> Result<Self> {
        Ok(Self {
            base_url,
            token,
            http: client()?,
        })
    }

    fn url(&self, path: &str) -> String {
        format!("{}{}", self.base_url.trim_end_matches('/'), path)
    }

    async fn check(r: reqwest::Response) -> Result<Value> {
        let status = r.status();
        let body = r.text().await.unwrap_or_default();
        if !status.is_success() {
            bail!("{} {}", status, body);
        }
        if body.is_empty() {
            return Ok(Value::Null);
        }
        Ok(serde_json::from_str(&body).unwrap_or(Value::String(body)))
    }

    pub async fn me(&self) -> Result<Value> {
        let r = self
            .http
            .get(self.url("/api/v1/me"))
            .bearer_auth(&self.token)
            .send()
            .await?;
        Self::check(r).await
    }

    pub async fn list_projects(
        &self,
        status: Option<&str>,
        tag: Option<&str>,
        q: Option<&str>,
        limit: Option<u32>,
    ) -> Result<Value> {
        let mut req = self
            .http
            .get(self.url("/api/v1/projects"))
            .bearer_auth(&self.token);
        let mut query: Vec<(&str, String)> = Vec::new();
        if let Some(s) = status {
            query.push(("status", s.to_string()));
        }
        if let Some(t) = tag {
            query.push(("tag", t.to_string()));
        }
        if let Some(q) = q {
            query.push(("q", q.to_string()));
        }
        if let Some(l) = limit {
            query.push(("limit", l.to_string()));
        }
        if !query.is_empty() {
            req = req.query(&query);
        }
        Self::check(req.send().await?).await
    }

    pub async fn get_project(&self, slug: &str) -> Result<Value> {
        let r = self
            .http
            .get(self.url(&format!("/api/v1/projects/{slug}")))
            .bearer_auth(&self.token)
            .send()
            .await?;
        Self::check(r).await
    }

    pub async fn patch_project(&self, slug: &str, body: &Value) -> Result<Value> {
        let r = self
            .http
            .patch(self.url(&format!("/api/v1/projects/{slug}")))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await?;
        Self::check(r).await
    }

    pub async fn switch_project(&self, slug: &str) -> Result<Value> {
        let r = self
            .http
            .post(self.url(&format!("/api/v1/projects/{slug}/switch")))
            .bearer_auth(&self.token)
            .send()
            .await?;
        Self::check(r).await
    }

    pub async fn get_context(&self, slug: &str) -> Result<Value> {
        let r = self
            .http
            .get(self.url(&format!("/api/v1/projects/{slug}/context")))
            .bearer_auth(&self.token)
            .send()
            .await?;
        Self::check(r).await
    }

    pub async fn patch_context(&self, slug: &str, body: &Value) -> Result<Value> {
        let r = self
            .http
            .patch(self.url(&format!("/api/v1/projects/{slug}/context")))
            .bearer_auth(&self.token)
            .json(body)
            .send()
            .await?;
        Self::check(r).await
    }
}
