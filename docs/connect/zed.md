# Connect Zed

**Requirements:** Zed 0.160+ with Context Server support.

## Setup

1. Zed → Settings → AI → Context Servers.
2. Click "Add Remote".
3. Enter URL: `https://vibecell.dev`.
4. Zed opens a browser tab for OAuth consent.
5. Pick workspace → "Allow & Connect".
6. The Vibecell context server appears in Zed's AI panel.

## Troubleshooting

**"Failed to connect to context server"** — Zed logs are in `~/.local/share/zed/logs/`. The most common cause is a stale token; remove and re-add the server.

**Revoke** — `vibecell.dev/settings/connections` → Revoke next to the Zed entry.
