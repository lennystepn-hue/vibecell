# Connect Windsurf

**Requirements:** Windsurf with Cascade MCP support.

## Setup

1. Windsurf → Settings → Cascade → MCP Servers.
2. Click "Add Remote Server".
3. Enter URL: `https://vibecell.dev`.
4. Windsurf opens a browser tab for OAuth consent.
5. Pick workspace → "Allow & Connect".
6. Cascade can now call Vibecell tools during conversations.

## Troubleshooting

**Server shows as disconnected** — Windsurf may cache a stale token. Remove the server entry, close and reopen Windsurf, then re-add.

**"Unauthorized" on tool call** — Token may have been revoked externally. Re-add the server to trigger a fresh OAuth flow.

**Revoke** — `vibecell.dev/settings/connections` → Revoke next to the Windsurf entry.
