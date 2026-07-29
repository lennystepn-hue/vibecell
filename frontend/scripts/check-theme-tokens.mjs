#!/usr/bin/env node
/**
 * Theme-integrity guard.
 *
 * Fails if a hardcoded colour literal appears anywhere under `src/`. Every
 * colour must come from a token in `assets/tokens.css` so all three themes
 * (default, terminal-green, paper) stay correct.
 *
 * Why this exists: before it, 267 literals lived in `style="…"` attributes
 * across 29 of 98 `.vue` files. Things like
 * `style="background:rgba(20,33,50,0.5)"` in the onboarding wizard rendered a
 * dark navy box on light paper — the paper and terminal-green themes shipped
 * visibly broken and nothing caught it. This is what catches it now.
 *
 * If you need a colour that no token provides, add the token — do not add an
 * exception. Exceptions below are for colours that must NOT follow the theme.
 *
 * Usage: node scripts/check-theme-tokens.mjs
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = join(fileURLToPath(new URL("../src", import.meta.url)));

/**
 * Colours that must stay literal in every theme, with the reason. Anything
 * not listed here is a failure.
 */
const EXEMPT_VALUES = new Map([
  ["#4285f4", "Google brand mark (sign-in button)"],
  ["#34a853", "Google brand mark (sign-in button)"],
  ["#fbbc05", "Google brand mark (sign-in button)"],
  ["#ea4335", "Google brand mark (sign-in button)"],
]);

/**
 * Files whose colours are identity data rather than chrome — they are
 * persisted, hashed, or otherwise must not change when the theme does.
 */
const EXEMPT_FILES = new Map([
  [
    "components/ui/ProjectOrb.vue",
    "Per-project identity palette, picked by slug hash. A project's colour " +
      "must not change when the user switches theme.",
  ],
  [
    "components/app/SidebarProjects.vue",
    "Group colour swatches. The user picks one and it is persisted to the " +
      "database, so the value has to be a literal.",
  ],
]);

// rgb()/rgba() with a numeric first argument — `rgb(var(--token) / 0.4)` is
// fine and must not match. Plus 3/6/8-digit hex.
const LITERAL = /rgba?\(\s*\d|#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?(?:[0-9a-fA-F]{2})?\b/g;
const HEX_AT = /#[0-9a-fA-F]{3,8}\b/;

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(vue|ts|css)$/.test(entry)) yield full;
  }
}

const failures = [];

for (const file of walk(SRC)) {
  const rel = relative(SRC, file).split(sep).join("/");
  // tokens.css is where literals are supposed to live.
  if (rel === "assets/tokens.css") continue;
  if (EXEMPT_FILES.has(rel)) continue;

  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, i) => {
    for (const match of line.matchAll(LITERAL)) {
      const text = match[0];
      const hex = text.match(HEX_AT)?.[0].toLowerCase();
      if (hex && EXEMPT_VALUES.has(hex)) continue;
      failures.push({ rel, line: i + 1, text, source: line.trim() });
    }
  });
}

if (failures.length === 0) {
  console.log("theme-tokens: ok — no hardcoded colour literals under src/");
  process.exit(0);
}

console.error(
  `\ntheme-tokens: ${failures.length} hardcoded colour literal(s) found.\n` +
    `Every colour must come from a token in src/assets/tokens.css so the\n` +
    `paper and terminal-green themes stay correct.\n`,
);
for (const f of failures) {
  console.error(`  ${f.rel}:${f.line}  ${f.text}`);
  console.error(`      ${f.source.slice(0, 120)}`);
}
console.error(
  `\nFixes, in order of preference:\n` +
    `  1. Use an existing token:      var(--signal-green), var(--fg-muted), …\n` +
    `  2. Need a one-off alpha?       rgb(var(--signal-green-rgb) / 0.25)\n` +
    `  3. Colour genuinely missing?   add it to tokens.css, in all three themes\n` +
    `  4. Must NOT follow the theme?  add it to EXEMPT_* in this script, with a reason\n`,
);
process.exit(1);
