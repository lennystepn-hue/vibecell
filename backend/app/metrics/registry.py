"""Prometheus metric registry for OAuth + MCP."""
from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge

REGISTRY = CollectorRegistry()

oauth_tokens_issued = Counter(
    "oauth_tokens_issued_total",
    "OAuth access tokens issued",
    labelnames=["client_name"],
    registry=REGISTRY,
)

oauth_authorize_outcomes = Counter(
    "oauth_authorize_redirects_total",
    "OAuth authorize redirects",
    labelnames=["outcome"],  # granted | denied | error
    registry=REGISTRY,
)

mcp_tool_calls = Counter(
    "mcp_tool_calls_total",
    "MCP tool calls",
    labelnames=["tool_name", "status"],
    registry=REGISTRY,
)

mcp_auth_failures = Counter(
    "mcp_auth_failures_total",
    "MCP auth middleware rejections",
    labelnames=["reason"],
    registry=REGISTRY,
)

mcp_active_connections = Gauge(
    "mcp_active_connections",
    "Currently-valid OAuth access tokens (non-expired, non-revoked)",
    registry=REGISTRY,
)
