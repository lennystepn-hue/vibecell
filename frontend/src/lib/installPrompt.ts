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
 *   1. Editor-agnostic — the AI picks whichever connection method fits its
 *      host, rather than us listing five and hoping it picks right.
 *   2. Self-contained — fresh AI context can run it cold. No "see above".
 *   3. Idempotent — running it again on an already-paired editor is a no-op.
 *
 * It used to be five numbered steps carrying the whole setup routine. That
 * text was frozen the moment a user copied it: anyone who pasted it in
 * January was still running January's instructions in June. The routine now
 * lives behind the `vibecell_onboard` MCP tool, server-side and editable,
 * and this shrank to the two lines needed to reach it.
 */

export const VIBECELL_INSTALL_PROMPT = `Connect to the Vibecell MCP server at https://vibecell.dev/mcp — pick whichever method your editor supports (remote HTTP if it has it, otherwise an mcp-remote bridge). The first tool call opens an OAuth consent in my browser; wait for me to approve it.

Then call \`vibecell_onboard\` with no arguments and follow what it tells you.`;

/** UI label used everywhere the prompt is offered as a tab/section. */
export const INSTALL_PROMPT_TAB_LABEL = "Paste into AI";

/** Sub-headline pitched at the user, not the AI. */
export const INSTALL_PROMPT_PITCH =
  "Skip the settings pages. Paste this into Claude, Cursor, Zed — any AI in your editor — and it'll install the MCP, run OAuth, read the operating manual, and brief itself on your project. ~10 seconds.";
