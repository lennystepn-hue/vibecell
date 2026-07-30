import { onMounted, ref } from "vue";

/**
 * How many MCP tools the backend actually registers.
 *
 * The landing page quoted "49" in three places — the hero stat strip, the
 * MCP catalogue heading, and an orb blurb — with a source comment reading:
 *
 *   // counts must sum to the live total (49 as of f82141c).
 *   // Re-bucket carefully when adding new tools so the hero stat strip
 *   // and these per-category counts stay consistent.
 *
 * That instruction failed the first time someone added a tool. A number a
 * human has to remember to update is a number that will be wrong.
 *
 * `/api/v1/status` already reports it, as the MCP component's message
 * ("50 tools registered"), so read it from there. The fallback matters:
 * a marketing page must render if the API is unreachable, and a slightly
 * stale number beats an empty one.
 */
const FALLBACK = 50;
const PATTERN = /(\d+)\s+tools?\s+registered/i;

interface StatusComponent {
  name: string;
  message: string | null;
}

export function useMcpToolCount() {
  const count = ref(FALLBACK);
  const live = ref(false);

  onMounted(async () => {
    try {
      const res = await fetch("/api/v1/status");
      if (!res.ok) return;
      const body = (await res.json()) as { components?: StatusComponent[] };
      for (const c of body.components ?? []) {
        const hit = c.message?.match(PATTERN);
        if (hit) {
          count.value = Number(hit[1]);
          live.value = true;
          return;
        }
      }
    } catch {
      /* offline or blocked — keep the fallback */
    }
  });

  return { count, live };
}
