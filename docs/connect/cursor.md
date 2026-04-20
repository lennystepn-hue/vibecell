# Connect Cursor

**Requirements:** Cursor 0.44+ (MCP remote server support).

## Setup

1. Cursor → Settings → Model Context Protocol.
2. Click "Add remote server".
3. Enter URL: `https://vibecell.dev`.
4. Cursor opens a browser tab for OAuth consent.
5. Pick workspace → "Allow & Connect".
6. Tools are available immediately in Cursor's agent.

## Troubleshooting

**No browser tab opens** — Ensure Cursor has network access and is not behind a proxy that strips `Location` headers.

**"MCP server error"** — Check Cursor's developer console (Help → Toggle Developer Tools) for the raw error. Most common cause: the token expired and needs re-auth; remove the server in Settings and re-add.

**Revoke** — `vibecell.dev/settings/connections` → Revoke next to the Cursor entry.
