/**
 * The "AI-paste" install prompt. Single source of truth so Welcome.vue,
 * ConnectModal.vue, and the public /install page all stay in sync.
 *
 * Why this exists: the slickest onboarding path isn't "user clicks 5 things
 * across 2 dialogs"; it's "user pastes one prompt into Claude/Cursor/Zed and
 * the AI does the wiring, the OAuth dance, the SKILL fetch, and the first
 * status read on its own." This file is the prompt itself.
 *
 * Constraints honoured by the wording below:
 *   1. Editor-agnostic — covers Claude Code, Claude Desktop, Cursor, Zed,
 *      Windsurf in one block. The AI picks whichever fits its host.
 *   2. Self-contained — fresh AI context can run it cold. No "see above".
 *   3. Idempotent — running it again on an already-paired editor is a
 *      no-op (the tool re-add fails harmlessly + the SKILL re-read is fine).
 *   4. Ends on a status report so the user gets concrete confirmation that
 *      something happened, not just "MCP added".
 */

export const VIBECELL_INSTALL_PROMPT = `Help me wire up Vibecell — my MCP-native project console.

1. Install the Vibecell MCP server. Pick the right command for the editor you're in:
   • Claude Code:  claude mcp add vibecell https://vibecell.dev/mcp --transport http --scope user
   • Claude Desktop:  open claude://add-connector?url=https%3A%2F%2Fvibecell.dev (or paste https://vibecell.dev under Settings → Connectors → Add Remote Server)
   • Cursor:  Settings → MCP → Add Remote Server → URL https://vibecell.dev/mcp
   • Zed / Windsurf:  add an mcp-remote context_servers entry pointing at https://vibecell.dev/mcp

2. The first tool call will open an OAuth consent in my browser — wait for me to approve there before continuing.

3. Once paired, call \`vibecell_ping\` then \`vibecell_active\` to load my active project context.

4. Fetch and read https://vibecell.dev/skill/SKILL.md — that's the operating manual. Follow its rules from now on (auto-log sessions, set_focus on topic shifts, tick todos from commit subjects, honour _audit_hint blocks).

5. Tell me: which project am I on, what's the current_focus, what open todos exist, and what's the obvious next move.`;

/** UI label used everywhere the prompt is offered as a tab/section. */
export const INSTALL_PROMPT_TAB_LABEL = "Paste into AI";

/** Sub-headline pitched at the user, not the AI. */
export const INSTALL_PROMPT_PITCH =
  "Skip the settings pages. Paste this into Claude, Cursor, Zed — any AI in your editor — and it'll install the MCP, run OAuth, read the operating manual, and brief itself on your project. ~10 seconds.";
