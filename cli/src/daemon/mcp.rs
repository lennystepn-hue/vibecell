//! HTTP MCP surface. Simplified for Claude Code's HTTP MCP client — three
//! endpoints: /mcp/v1/server, /mcp/v1/tools/list, /mcp/v1/tools/call.

use std::sync::Arc;

use anyhow::Result;
use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::{self, Next},
    response::IntoResponse,
    routing::{get, post},
    Json, Router,
};
use serde_json::{json, Value};
use tokio::net::TcpListener;

use crate::cloud;

pub struct AppState {
    pub token: String,
    pub cloud: cloud::Client,
}

pub async fn serve(state: Arc<AppState>) -> Result<()> {
    let app = Router::new()
        .route("/mcp/v1/server", get(server_info))
        .route("/mcp/v1/tools/list", get(tools_list))
        .route("/mcp/v1/tools/call", post(tools_call))
        .layer(middleware::from_fn_with_state(
            state.clone(),
            auth_middleware,
        ))
        .with_state(state);

    let listener = TcpListener::bind("127.0.0.1:7421").await?;
    tracing::info!("MCP listening on http://127.0.0.1:7421");

    // Ctrl+C graceful shutdown.
    let shutdown = async {
        let _ = tokio::signal::ctrl_c().await;
        println!("\ndaemon stopped");
    };
    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown)
        .await?;
    Ok(())
}

async fn auth_middleware(
    State(state): State<Arc<AppState>>,
    req: Request,
    next: Next,
) -> impl IntoResponse {
    let header = req
        .headers()
        .get("authorization")
        .and_then(|h| h.to_str().ok())
        .unwrap_or_default();
    let expected = format!("Bearer {}", state.token);
    if header != expected {
        return (
            StatusCode::UNAUTHORIZED,
            Json(json!({"error": "invalid bearer"})),
        )
            .into_response();
    }
    next.run(req).await
}

async fn server_info() -> Json<Value> {
    Json(json!({
        "name": "hangar",
        "version": env!("CARGO_PKG_VERSION"),
        "protocolVersion": "2024-11-05"
    }))
}

async fn tools_list(State(_state): State<Arc<AppState>>) -> Json<Value> {
    Json(json!({ "tools": super::tools::tool_specs() }))
}

#[derive(serde::Deserialize)]
struct ToolCallReq {
    name: String,
    #[serde(default)]
    arguments: Value,
}

async fn tools_call(
    State(state): State<Arc<AppState>>,
    Json(req): Json<ToolCallReq>,
) -> Json<Value> {
    match super::tools::dispatch(&state, &req.name, &req.arguments).await {
        Ok(text) => Json(json!({ "content": [{"type": "text", "text": text}] })),
        Err(e) => Json(json!({
            "content": [{"type": "text", "text": format!("error: {e}")}],
            "isError": true
        })),
    }
}
