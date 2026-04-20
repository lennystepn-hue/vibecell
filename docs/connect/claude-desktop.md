# Connect Claude Desktop

**Requirements:** Claude Desktop 0.X+ with MCP connector support.

## One-click (recommended)

1. Open [vibecell.dev/settings/connections](https://vibecell.dev/settings/connections).
2. Click "Connect another app" → "Claude Desktop" tab → "Try one-click".
3. Claude Desktop opens; confirm "Add Vibecell as connector?".
4. A browser tab opens at vibecell.dev; pick your workspace → "Allow & Connect".
5. Claude Desktop now lists vibecell as a connected server. 17 tools available.

## Manual

If the one-click button does nothing:

1. Open Claude Desktop → Settings → Connectors → "Add Remote Server".
2. Enter URL: `https://vibecell.dev`.
3. Desktop discovers OAuth, opens a browser tab to sign in + consent.
4. Consent screen: pick workspace → "Allow & Connect".

## Troubleshooting

**"Server refused connection"** — Vibecell is not reachable from your network. Check `curl https://vibecell.dev/.well-known/oauth-authorization-server`.

**"Invalid redirect_uri"** — Claude Desktop has rotated its loopback port. Delete the connector in Desktop, retry.

**"Scope insufficient"** — Your token was issued before a scope change. Revoke at `vibecell.dev/settings/connections` and reconnect.
