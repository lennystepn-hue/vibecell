//! MCP tool specs + dispatcher. Implementations arrive in commit 3.

use anyhow::{bail, Result};
use serde_json::{json, Value};

use crate::daemon::mcp::AppState;

pub fn tool_specs() -> Value {
    json!([
        {
            "name": "hangar.ping",
            "description": "Health check. Returns ok=true, version, and active project slug (if any).",
            "inputSchema": {"type": "object", "properties": {}, "required": []}
        }
    ])
}

pub async fn dispatch(state: &AppState, name: &str, _args: &Value) -> Result<String> {
    match name {
        "hangar.ping" => ping(state).await,
        _ => bail!("unknown tool: {name}"),
    }
}

async fn ping(_state: &AppState) -> Result<String> {
    Ok(json!({
        "ok": true,
        "version": env!("CARGO_PKG_VERSION"),
        "active_slug": serde_json::Value::Null,
    })
    .to_string())
}
