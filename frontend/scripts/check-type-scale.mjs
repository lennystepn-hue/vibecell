#!/usr/bin/env node
/**
 * Type-scale guard.
 *
 * Fails if a Tailwind arbitrary type value appears where the scale already
 * has a step: `text-[11px]`, `tracking-[0.15em]`. Sizes come from
 * `tailwind.config.ts` → `fontSize`; letter-spacing from `letterSpacing`.
 *
 * Why this exists: the scale was complete and well-designed, and 203 places
 * across 50 files bypassed it anyway. `text-[11px]` was written 80 times
 * while the `micro` step that means exactly that was used zero times.
 * Fifty-seven letter-spacings were spread across eight ad-hoc values nobody
 * could tell apart (0.14em vs 0.15em).
 *
 * Scope: the scale governs running text, labels and numerals — 9px to 14px.
 * Decorative glyph sizing (the ◈ wordmark, the big status symbol on
 * /status) is layout rather than typography, so sizes above the scale are
 * left alone deliberately. If you find yourself wanting a 15px body text,
 * the answer is a scale step, not an arbitrary value.
 *
 * Usage: node scripts/check-type-scale.mjs
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../src", import.meta.url));

/** px → scale step. Mirrors `fontSize` in tailwind.config.ts. */
const SIZES = {
  "9px": "pico", "10px": "nano", "11px": "micro",
  "12px": "small", "13px": "body", "14px": "section",
};
/** em → step. Mirrors `letterSpacing` in tailwind.config.ts. */
const TRACKING = {
  "0.06em": "label", "0.08em": "label",
  "0.1em": "caps", "0.12em": "caps", "0.14em": "caps", "0.15em": "caps",
  "0.18em": "wide", "0.2em": "wide",
};

function* walk(dir) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.(vue|ts)$/.test(entry)) yield full;
  }
}

const failures = [];

for (const file of walk(SRC)) {
  const rel = relative(SRC, file).split(sep).join("/");
  readFileSync(file, "utf8").split(/\r?\n/).forEach((line, i) => {
    for (const m of line.matchAll(/\btext-\[(\d+px)\]/g)) {
      const step = SIZES[m[1]];
      if (step) failures.push({ rel, line: i + 1, found: m[0], want: `text-${step}` });
    }
    for (const m of line.matchAll(/\btracking-\[([\d.]+em)\]/g)) {
      const step = TRACKING[m[1]];
      if (step) failures.push({ rel, line: i + 1, found: m[0], want: `tracking-${step}` });
    }
  });
}

if (failures.length === 0) {
  console.log("type-scale: ok — no arbitrary type values inside the scale's range");
  process.exit(0);
}

console.error(`\ntype-scale: ${failures.length} arbitrary type value(s) found.\n`);
for (const f of failures) {
  console.error(`  ${f.rel}:${f.line}  ${f.found}  →  use ${f.want}`);
}
console.error(
  `\nThe scale lives in tailwind.config.ts. If none of its steps fit, add one\n` +
    `there rather than writing the pixel value inline.\n`,
);
process.exit(1);
