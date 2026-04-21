import { defineStore } from "pinia";
import { computed, ref } from "vue";

export interface PresenceEntry {
  slug: string;
  tool: string | null;
  at: string | null;  // ISO
  age_seconds: number;
}

/**
 * Ephemeral MCP presence — which projects Claude is actively running tool
 * calls against in the active workspace. Backed by Redis on the server with a
 * 120-second TTL; the frontend just polls and renders live dots.
 */
export const usePresenceStore = defineStore("presence", () => {
  const entries = ref<PresenceEntry[]>([]);
  const lastFetchedAt = ref<number | null>(null);
  let pollId: ReturnType<typeof setInterval> | null = null;

  const byslug = computed(() => {
    const m = new Map<string, PresenceEntry>();
    for (const e of entries.value) m.set(e.slug, e);
    return m;
  });

  function isLive(slug: string): boolean {
    const e = byslug.value.get(slug);
    if (!e) return false;
    // Age-out on the client too — avoids stale "live" dots if the poll pauses
    // (e.g. tab inactive) while the server-side key has expired.
    return e.age_seconds < 150;  // 2.5m window; a bit more forgiving than server TTL
  }

  function toolFor(slug: string): string | null {
    return byslug.value.get(slug)?.tool ?? null;
  }

  function ageFor(slug: string): number | null {
    return byslug.value.get(slug)?.age_seconds ?? null;
  }

  async function refresh(): Promise<void> {
    try {
      const r = await fetch("/api/v1/workspaces/me/presence", {
        credentials: "include",
      });
      if (!r.ok) {
        entries.value = [];
        return;
      }
      const json = (await r.json()) as { entries: PresenceEntry[] };
      entries.value = json.entries ?? [];
      lastFetchedAt.value = Date.now();
    } catch {
      // Network hiccups are fine — keep the previous list; it'll age out.
    }
  }

  function start(pollMs = 5000): void {
    if (pollId) return;
    refresh();
    pollId = setInterval(refresh, pollMs);
  }

  function stop(): void {
    if (pollId) {
      clearInterval(pollId);
      pollId = null;
    }
  }

  return { entries, lastFetchedAt, isLive, toolFor, ageFor, refresh, start, stop };
});
