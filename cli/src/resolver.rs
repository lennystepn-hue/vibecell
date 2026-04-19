//! Secret-reference resolvers.
//!
//! Each kind maps the stored `reference` string to a plaintext value (except
//! ssh_agent, which is consumed as-is by the caller). Resolution for
//! `inline_encrypted` roundtrips through the backend /resolve endpoint — the
//! CLI never holds workspace DEKs.
//!
//! Until `hangar run` and the MCP tool wire this in (commit 5/6), most
//! functions appear unused — the module-level allow is removed then.
#![allow(dead_code)]

use anyhow::{bail, Context, Result};

pub fn kind_from_reference(reference: &str) -> Option<&'static str> {
    if reference.starts_with("op://") {
        Some("op")
    } else if reference.starts_with("bw://") {
        Some("bw")
    } else if reference.starts_with("ssh-agent://") {
        Some("ssh_agent")
    } else if reference.starts_with("env://") {
        Some("env_path")
    } else if reference.starts_with("keychain://") {
        Some("keychain")
    } else {
        None
    }
}

pub async fn resolve(
    client: &crate::cloud::Client,
    project_slug: &str,
    kind: &str,
    reference: &str,
    label: &str,
) -> Result<String> {
    match kind {
        "inline_encrypted" => client.get_secret_value(project_slug, label).await,
        "op" => resolve_op(reference).await,
        "bw" => resolve_bw(reference).await,
        "ssh_agent" => {
            bail!("ssh_agent secrets don't resolve to a value — configure the child via SSH_AUTH_SOCK instead")
        }
        "env_path" => resolve_env(reference),
        "keychain" => {
            bail!("keychain kind not supported yet — use inline_encrypted or op for now")
        }
        other => bail!("unknown secret kind: {}", other),
    }
}

async fn resolve_op(reference: &str) -> Result<String> {
    // op:// path goes directly to `op read`
    let output = tokio::process::Command::new("op")
        .args(["read", reference])
        .output()
        .await
        .context("spawning `op` — is the 1Password CLI installed and signed in?")?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!("op read failed: {}", stderr.trim());
    }
    Ok(String::from_utf8(output.stdout)?.trim_end().to_string())
}

async fn resolve_bw(reference: &str) -> Result<String> {
    // reference format: bw://<item>[/<field>]
    let inner = reference.trim_start_matches("bw://");
    let (item, field) = match inner.split_once('/') {
        Some((i, f)) => (i, f),
        None => (inner, "password"),
    };
    let output = tokio::process::Command::new("bw")
        .args(["get", field, item])
        .output()
        .await
        .context("spawning `bw` — is the Bitwarden CLI installed and unlocked?")?;
    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        bail!(
            "bw get failed: {} (is BW_SESSION set and unlocked?)",
            stderr.trim()
        );
    }
    Ok(String::from_utf8(output.stdout)?.trim_end().to_string())
}

fn resolve_env(reference: &str) -> Result<String> {
    let name = reference.trim_start_matches("env://");
    std::env::var(name).with_context(|| format!("env var {name} not set"))
}
