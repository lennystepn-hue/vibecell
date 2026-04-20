# Connect your editor to Vibecell

Vibecell works with any MCP-compatible client. Pick yours:

- [Claude Desktop](./claude-desktop.md)
- [Claude Code](./claude-code.md)
- [Cursor](./cursor.md)
- [Zed](./zed.md)
- [Windsurf](./windsurf.md)

## What gets connected

Once authorized, your client can call 17 tools against your active Vibecell workspace:

**Read** — `ping`, `active`, `list`, `get`, `brief`, `search`, `recent_projects`, `claude_md`, `handover`  
**Write** — `switch`, `log_session`, `update_context`, `decision`, `idea`, `note_append`, `ship`, `status`

## What stays local

`vibecell.run` — execute saved project commands with secret resolution — only works with the local
CLI (install via `curl vibecell.dev/install.sh | sh`). Remote clients cannot execute on your
machine by design.

## Revoking access

`vibecell.dev/settings/connections` shows every connected client with a revoke button.
Disconnection is immediate.
