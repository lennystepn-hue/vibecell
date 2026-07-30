import { describe, expect, it } from "vitest";

import { DEFAULT_LAYOUT, WIDGETS } from "../widget-registry";
import {
  FAMILY_ACCENT,
  FAMILY_ACCENT_RGB,
  WIDGET_IDENTITY,
  identityFor,
} from "../widget-identity";

describe("widget identity", () => {
  it("covers every registered widget", () => {
    // A card with no identity renders an untinted header and looks like a
    // mistake rather than a choice.
    const missing = Object.keys(WIDGETS).filter((id) => !identityFor(id));
    expect(missing).toEqual([]);
  });

  it("covers every widget in the default layout", () => {
    const missing = DEFAULT_LAYOUT.map((l) => l.i).filter((id) => !identityFor(id));
    expect(missing).toEqual([]);
  });

  it("gives every card a distinct glyph", () => {
    // `health` and `sessions` both used ◎ before this map existed, which made
    // them indistinguishable in the one place glyphs were rendered at all.
    const glyphs = Object.values(WIDGET_IDENTITY).map((i) => i.glyph);
    expect(new Set(glyphs).size).toBe(glyphs.length);
  });

  it("uses no colour emoji", () => {
    // ✨ on brief and 🔐 on secrets survived a deliberate emoji purge because
    // they lived in a registry field nobody rendered. The cockpit language is
    // geometric; a sparkle says "magic" where the rest says "instrument".
    //
    // The property that matters is `Emoji_Presentation` — "renders in colour
    // by default" — not `Extended_Pictographic`, which also covers plain
    // dingbats like ☑ ✎ ↗ that render monochrome in a mono font and belong
    // here. Checked the wrong one first and it failed on four glyphs that
    // were perfectly fine.
    const colourEmoji = /\p{Emoji_Presentation}/u;
    const offenders = Object.entries(WIDGET_IDENTITY)
      .filter(([, i]) => colourEmoji.test(i.glyph))
      .map(([id]) => id);
    expect(offenders).toEqual([]);
  });

  it("maps every family to both an accent and a channel token", () => {
    for (const { family } of Object.values(WIDGET_IDENTITY)) {
      expect(FAMILY_ACCENT[family]).toMatch(/^--signal-/);
      expect(FAMILY_ACCENT_RGB[family]).toMatch(/^--signal-.*-rgb$/);
    }
  });

  it("keeps amber and red out of the family palette", () => {
    // Those two are reserved for state — a failing probe, a blocker — so
    // that when one appears on the console it means something. Spending them
    // on card identity would make a real alert indistinguishable from a
    // decorative header.
    const used = Object.values(FAMILY_ACCENT);
    expect(used).not.toContain("--signal-amber");
    expect(used).not.toContain("--signal-red");
  });

  it("stays at four families — six would read as a rainbow", () => {
    const families = new Set(Object.values(WIDGET_IDENTITY).map((i) => i.family));
    expect(families.size).toBeLessThanOrEqual(4);
  });
});
