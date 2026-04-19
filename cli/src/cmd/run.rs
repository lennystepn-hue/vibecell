//! `hangar run <label>` — execute a saved project command.
//!
//! Flow:
//! 1. Fetch project aggregate (`commands` list) + project secrets.
//! 2. Find the command by label (case-insensitive).
//! 3. For each `@<label>` placeholder in the command string, resolve against
//!    the project's secret-refs (inline via backend /resolve, op/bw via the
//!    resolver module).
//! 4. Spawn a shell subprocess with the resolved command; inherit stdio so
//!    the user sees output live.
//! 5. Print a final "ok exit N (ts)" line.
//!
//! Security: the resolved command never gets logged. `tracing::debug!`
//! logs only the template (pre-substitution).

use anyhow::{bail, Context, Result};
use std::time::Instant;

use crate::{cloud, config, keychain, resolver};

pub async fn run(label: String, project: Option<String>) -> Result<()> {
    let client = build_client()?;
    let project_slug = resolve_project_slug(project)?;

    let full = client.get_project(&project_slug).await?;
    let cmds = full
        .get("commands")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();

    let target = cmds
        .iter()
        .find(|c| {
            c.get("label")
                .and_then(|v| v.as_str())
                .map(|s| s.eq_ignore_ascii_case(&label))
                .unwrap_or(false)
        })
        .with_context(|| {
            let available: Vec<String> = cmds
                .iter()
                .filter_map(|c| {
                    c.get("label")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string())
                })
                .collect();
            if available.is_empty() {
                format!("no command {label:?} on project {project_slug} (no commands saved)")
            } else {
                format!(
                    "no command {label:?} on project {project_slug}; available: {}",
                    available.join(", ")
                )
            }
        })?;

    let cmd_str = target
        .get("command")
        .and_then(|v| v.as_str())
        .context("command row missing `command` string")?;
    let actual_label = target
        .get("label")
        .and_then(|v| v.as_str())
        .unwrap_or(&label);

    tracing::debug!(template = %cmd_str, "resolving command");

    // Resolve @labels.
    let secrets = client.list_secrets(&project_slug).await?;
    let placeholders = extract_placeholders(cmd_str);

    let mut resolved = cmd_str.to_string();
    for ph in &placeholders {
        let row = secrets
            .iter()
            .find(|s| s.label == *ph)
            .with_context(|| format!("secret {ph:?} not found on project {project_slug}"))?;
        println!(
            "-> resolving @{} via {}{}",
            ph,
            row.kind,
            match row.kind.as_str() {
                "op" => format!(" ({})", row.reference),
                _ => String::new(),
            }
        );
        let value = resolver::resolve(
            &client,
            &project_slug,
            &row.kind,
            &row.reference,
            &row.label,
        )
        .await
        .with_context(|| format!("resolving @{ph}"))?;
        resolved = resolved.replace(&format!("@{ph}"), &value);
    }

    println!("-> executing: {actual_label}");
    let started = Instant::now();
    let status = spawn_shell(&resolved).await?;
    let dur = started.elapsed();

    let symbol = if status.success() { "ok" } else { "!!" };
    let code = status.code().unwrap_or(-1);
    println!("{symbol} exit {code} ({:.1}s)", dur.as_secs_f64());

    if !status.success() {
        std::process::exit(code);
    }
    Ok(())
}

fn build_client() -> Result<cloud::Client> {
    let cfg = config::load()?;
    let base_url = cfg
        .base_url
        .clone()
        .unwrap_or_else(config::default_base_url);
    let device_id = cfg
        .device_id
        .as_deref()
        .context("not paired — run `hangar pair` first")?;
    let token = keychain::load_token(&base_url, device_id)
        .ok()
        .or(cfg.bearer_token_fallback)
        .context("no bearer token — run `hangar pair` again")?;
    cloud::Client::new(base_url, token)
}

fn resolve_project_slug(explicit: Option<String>) -> Result<String> {
    if let Some(s) = explicit {
        return Ok(s);
    }
    let conn = crate::cache::open()?;
    if let Some(s) = crate::cache::get_active_slug(&conn)? {
        return Ok(s);
    }
    bail!("no active project — pass --project <slug> or run `hangar sync` + `hangar switch`")
}

/// Extract `@label` tokens from `s`. Matches `@` followed by
/// `[A-Za-z0-9_-]+`; e.g. `@anthropic-key` or `@foo_bar`.
pub fn extract_placeholders(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let bytes = s.as_bytes();
    let mut i = 0usize;
    while i < bytes.len() {
        if bytes[i] == b'@' {
            let start = i + 1;
            let mut j = start;
            while j < bytes.len() {
                let c = bytes[j];
                if c.is_ascii_alphanumeric() || c == b'_' || c == b'-' {
                    j += 1;
                } else {
                    break;
                }
            }
            if j > start {
                let label = &s[start..j];
                let label = label.to_string();
                if !out.contains(&label) {
                    out.push(label);
                }
                i = j;
                continue;
            }
        }
        i += 1;
    }
    out
}

#[cfg(unix)]
async fn spawn_shell(command: &str) -> Result<std::process::ExitStatus> {
    use std::process::Stdio;
    let status = tokio::process::Command::new("sh")
        .arg("-c")
        .arg(command)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .await?;
    Ok(status)
}

#[cfg(windows)]
async fn spawn_shell(command: &str) -> Result<std::process::ExitStatus> {
    use std::process::Stdio;
    let status = tokio::process::Command::new("cmd")
        .arg("/C")
        .arg(command)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .await?;
    Ok(status)
}

// ---------------------------------------------------------------------------
// Capture variant — used by the MCP `hangar.run` tool, returns tails + code.
// ---------------------------------------------------------------------------

#[allow(dead_code)] // surfaced through MCP (commit 6)
pub struct RunCapture {
    pub exit_code: i32,
    pub stdout_tail: String,
    pub stderr_tail: String,
    pub duration_ms: u64,
}

#[allow(dead_code)]
pub async fn run_capture(
    client: &cloud::Client,
    project_slug: &str,
    label: &str,
) -> Result<RunCapture> {
    let full = client.get_project(project_slug).await?;
    let cmds = full
        .get("commands")
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default();
    let target = cmds
        .iter()
        .find(|c| {
            c.get("label")
                .and_then(|v| v.as_str())
                .map(|s| s.eq_ignore_ascii_case(label))
                .unwrap_or(false)
        })
        .with_context(|| format!("no command {label:?} on project {project_slug}"))?;
    let cmd_str = target
        .get("command")
        .and_then(|v| v.as_str())
        .context("command row missing `command`")?;

    let secrets = client.list_secrets(project_slug).await?;
    let placeholders = extract_placeholders(cmd_str);

    let mut resolved = cmd_str.to_string();
    for ph in &placeholders {
        let row = secrets
            .iter()
            .find(|s| s.label == *ph)
            .with_context(|| format!("secret {ph:?} not found on project {project_slug}"))?;
        let value = resolver::resolve(client, project_slug, &row.kind, &row.reference, &row.label)
            .await
            .with_context(|| format!("resolving @{ph}"))?;
        resolved = resolved.replace(&format!("@{ph}"), &value);
    }

    let started = Instant::now();
    let output = capture_shell(&resolved).await?;
    let dur = started.elapsed();

    Ok(RunCapture {
        exit_code: output.status.code().unwrap_or(-1),
        stdout_tail: tail(&output.stdout, 4096),
        stderr_tail: tail(&output.stderr, 4096),
        duration_ms: dur.as_millis() as u64,
    })
}

#[cfg(unix)]
#[allow(dead_code)]
async fn capture_shell(command: &str) -> Result<std::process::Output> {
    let timeout = std::time::Duration::from_secs(300);
    let fut = tokio::process::Command::new("sh")
        .arg("-c")
        .arg(command)
        .output();
    let out = tokio::time::timeout(timeout, fut)
        .await
        .context("command timed out after 5m")??;
    Ok(out)
}

#[cfg(windows)]
#[allow(dead_code)]
async fn capture_shell(command: &str) -> Result<std::process::Output> {
    let timeout = std::time::Duration::from_secs(300);
    let fut = tokio::process::Command::new("cmd")
        .arg("/C")
        .arg(command)
        .output();
    let out = tokio::time::timeout(timeout, fut)
        .await
        .context("command timed out after 5m")??;
    Ok(out)
}

#[allow(dead_code)]
fn tail(bytes: &[u8], n: usize) -> String {
    let start = bytes.len().saturating_sub(n);
    String::from_utf8_lossy(&bytes[start..]).to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn placeholders_basic() {
        assert_eq!(
            extract_placeholders("ANTHROPIC_API_KEY=@anthropic-key deploy.sh"),
            vec!["anthropic-key".to_string()],
        );
    }

    #[test]
    fn placeholders_multiple_unique() {
        assert_eq!(
            extract_placeholders("A=@foo B=@bar @foo"),
            vec!["foo".to_string(), "bar".to_string()],
        );
    }

    #[test]
    fn placeholders_known_ambiguity() {
        // Known simplification: `@` followed by alnum is always treated as a
        // placeholder. Emails inside command strings would collide — users
        // must quote them or the resolver fails with "secret example not found".
        assert_eq!(
            extract_placeholders("echo me@example"),
            vec!["example".to_string()],
        );
    }

    #[test]
    fn placeholders_stop_at_dot() {
        // `.` is not a label-char, so `@foo.bar` yields `foo` not `foo.bar`.
        assert_eq!(
            extract_placeholders("echo @foo.bar"),
            vec!["foo".to_string()],
        );
    }
}
