//! `hangar secret set/list/remove` — manage per-project secret references.
//!
//! `set` auto-detects kind from the reference prefix when `--ref` is used.
//! Positional `value` (no `--ref`) stores as inline_encrypted. With neither,
//! we prompt for hidden input and store as inline_encrypted.

use anyhow::{Context, Result};
use clap::Subcommand;

use crate::{cloud, config, keychain, resolver};

#[derive(Subcommand, Debug)]
pub enum SecretCommand {
    /// Add or update a project secret.
    Set {
        /// Label (unique per project, e.g. "anthropic-key").
        label: String,
        /// Inline value. Stored encrypted with the workspace DEK on hangar.dev.
        value: Option<String>,
        /// External reference (e.g. op://Private/Anthropic/api-key).
        #[arg(long = "ref")]
        reference: Option<String>,
        /// Project slug. Defaults to the active project from local cache.
        #[arg(long)]
        project: Option<String>,
    },
    /// List secrets on a project.
    List {
        #[arg(long)]
        project: Option<String>,
    },
    /// Remove a secret from a project.
    Remove {
        label: String,
        #[arg(long)]
        project: Option<String>,
    },
}

pub async fn run(cmd: SecretCommand) -> Result<()> {
    let client = build_client()?;
    match cmd {
        SecretCommand::Set {
            label,
            value,
            reference,
            project,
        } => set(client, label, value, reference, project).await,
        SecretCommand::List { project } => list(client, project).await,
        SecretCommand::Remove { label, project } => remove(client, label, project).await,
    }
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
    anyhow::bail!(
        "no active project — pass --project <slug> or run `hangar sync` + `hangar switch`"
    )
}

async fn set(
    client: cloud::Client,
    label: String,
    value: Option<String>,
    reference: Option<String>,
    project: Option<String>,
) -> Result<()> {
    let project_slug = resolve_project_slug(project)?;

    let (kind, reference) = match (value, reference) {
        (_, Some(r)) => {
            let kind = resolver::kind_from_reference(&r).with_context(|| {
                format!(
                    "cannot infer kind from reference {r:?} — expected op:// bw:// ssh-agent:// env:// keychain://"
                )
            })?;
            (kind.to_string(), r)
        }
        (Some(v), None) => ("inline_encrypted".to_string(), v),
        (None, None) => {
            // Hidden prompt.
            let v = rpassword::prompt_password(format!("value for {label}: "))?;
            if v.is_empty() {
                anyhow::bail!("empty value — aborting");
            }
            ("inline_encrypted".to_string(), v)
        }
    };

    let row = client
        .add_secret(&project_slug, &label, &kind, &reference)
        .await?;

    match kind.as_str() {
        "inline_encrypted" => println!("ok stored encrypted on hangar.dev ({})", row.label),
        _ => println!(
            "ok stored reference (resolved at exec time) — {} ({})",
            row.label, kind
        ),
    }
    Ok(())
}

async fn list(client: cloud::Client, project: Option<String>) -> Result<()> {
    let project_slug = resolve_project_slug(project)?;
    let rows = client.list_secrets(&project_slug).await?;
    if rows.is_empty() {
        println!("(no secrets on project {project_slug})");
        return Ok(());
    }
    let label_w = rows.iter().map(|r| r.label.len()).max().unwrap_or(8).max(8);
    let kind_w = rows.iter().map(|r| r.kind.len()).max().unwrap_or(6).max(6);
    for r in rows {
        println!(
            "{:<lw$}  {:<kw$}  {}",
            r.label,
            r.kind,
            r.reference,
            lw = label_w,
            kw = kind_w
        );
    }
    Ok(())
}

async fn remove(client: cloud::Client, label: String, project: Option<String>) -> Result<()> {
    let project_slug = resolve_project_slug(project)?;
    client.remove_secret(&project_slug, &label).await?;
    println!("ok removed {label}");
    Ok(())
}
