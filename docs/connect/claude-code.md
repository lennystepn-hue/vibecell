# Connect Claude Code (CLI)

## Remote (zero-install beyond Claude Code itself)

Drop in your project root:

```json
// .mcp.json
{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "https://vibecell.dev/mcp"
    }
  }
}
```

Restart Claude Code in that directory. First tool call triggers OAuth:
browser opens → pick workspace → allow. Token is cached under
`~/.claude/mcp-auth/vibecell.dev.json`.

## Local (for `vibecell.run` — command execution with secrets)

```bash
curl vibecell.dev/install.sh | sh
hangar pair
hangar daemon start
```

Then in `.mcp.json`:

```json
{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "http://127.0.0.1:7421/mcp/v1",
      "headers": { "Authorization": "Bearer ${HANGAR_MCP_TOKEN}" }
    }
  }
}
```

The local daemon exposes all 18 tools including `vibecell.run`.

## Troubleshooting

**OAuth loop / browser keeps opening** — Delete `~/.claude/mcp-auth/vibecell.dev.json` and retry.

**"Tool not found"** — Confirm `type: "http"` not `"stdio"` in `.mcp.json`. Claude Code only supports streamable HTTP for remote servers.
