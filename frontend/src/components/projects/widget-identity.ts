/**
 * Visual identity per card: a glyph and an accent colour.
 *
 * The console renders sixteen cards with identical chrome — same glass, same
 * border, same padding, same grey `//label`. You end up *reading* every card
 * to find one instead of *recognising* it. Sixteen identical grey boxes is
 * the actual complaint, and no amount of spacing fixes it.
 *
 * Two dimensions, both learnable:
 *
 *   glyph   what this card is — geometric, in keeping with the cockpit
 *           language (◈ ◢ ◇), never emoji. Two emoji had crept in (✨ on
 *           brief, 🔐 on secrets) despite emoji being deliberately removed
 *           elsewhere; both are gone. `health` and `sessions` also shared
 *           ◎, so they were indistinguishable even in the add-widget menu
 *           where the glyphs were the only thing rendered.
 *
 *   accent  which family this belongs to. Four families, chosen by how the
 *           console is used rather than by what the data is:
 *
 *             work       green    what you act on now
 *             ops        teal     what runs, and where
 *             history    blue     what happened, and why
 *             reference  violet   what it is
 *
 * Four colours across sixteen cards reads as organised. Six would read as a
 * rainbow, which is why `amber` and `red` stay out of this map entirely —
 * they are reserved for state (a failing probe, a blocker) so that when one
 * appears it means something.
 *
 * Single source of truth: the registry uses it for the add-widget menu, the
 * card components use it for their own header. Defining it twice is how the
 * glyphs drifted into emoji in the first place.
 */

export type WidgetFamily = "work" | "ops" | "history" | "reference";

export interface WidgetIdentity {
  glyph: string;
  family: WidgetFamily;
}

/** Family → the CSS custom property that tints the glyph. */
export const FAMILY_ACCENT: Record<WidgetFamily, string> = {
  work: "--signal-green",
  ops: "--signal-teal",
  history: "--signal-blue",
  reference: "--signal-violet",
};

/** Family → channel token, for the tinted chip behind the glyph. */
export const FAMILY_ACCENT_RGB: Record<WidgetFamily, string> = {
  work: "--signal-green-rgb",
  ops: "--signal-teal-rgb",
  history: "--signal-blue-rgb",
  reference: "--signal-violet-rgb",
};

export const WIDGET_IDENTITY: Record<string, WidgetIdentity> = {
  // ── work ────────────────────────────────────────────────────────────────
  focus: { glyph: "◆", family: "work" },
  todos: { glyph: "☑", family: "work" },

  // ── ops ─────────────────────────────────────────────────────────────────
  // ◎ was shared with sessions; health keeps it because a probe target reads
  // as a ring far better than a log entry does.
  health: { glyph: "◎", family: "ops" },
  environments: { glyph: "⌁", family: "ops" },
  infra: { glyph: "◇", family: "ops" },
  // was 🔐 — the only pictographic glyph left after the emoji purge.
  secrets: { glyph: "⚿", family: "ops" },

  // ── history ─────────────────────────────────────────────────────────────
  sessions: { glyph: "❯", family: "history" },
  decisions: { glyph: "⟁", family: "history" },
  launches: { glyph: "▲", family: "history" },
  activity: { glyph: "⟐", family: "history" },

  // ── reference ───────────────────────────────────────────────────────────
  // was ✨ — AI-authored, but a sparkle says "magic" where the rest of the
  // interface says "instrument".
  brief: { glyph: "◈", family: "reference" },
  primer: { glyph: "▤", family: "reference" },
  stack: { glyph: "≡", family: "reference" },
  tags: { glyph: "#", family: "reference" },
  "links-commands": { glyph: "↗", family: "reference" },
  notes: { glyph: "✎", family: "reference" },
};

export function identityFor(id: string): WidgetIdentity | undefined {
  return WIDGET_IDENTITY[id];
}
