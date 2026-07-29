import { defineStore } from "pinia";
import { computed, ref } from "vue";

/**
 * Live onboarding progress.
 *
 * Backs the narration on the setup screen: "✓ gekoppelt · 14 Repos gefunden ·
 * ◐ butlr wird gelesen". Frames arrive over the user-scoped SSE stream from
 * `/api/v1/onboarding/stream` while `hangar setup` (#5) and
 * `vibecell_onboard` (#6) work on the user's machine.
 *
 * The screen itself lands in #7. This store ships first so that screen has
 * something real to render against rather than an animation.
 *
 * Reconnect behaviour mirrors `composables/useProjectLive.ts`: EventSource
 * retries on its own for network blips but gives up on a 4xx, so we reopen
 * explicitly with backoff.
 */

/** Mirrors `OnboardingEvent` in backend/app/services/onboarding_events.py. */
export type OnboardingEventType =
  | "stream.open"
  | "paired"
  | "client.configured"
  | "scan.started"
  | "project.created"
  | "project.enriched"
  | "done";

export interface OnboardingEvent {
  type: OnboardingEventType;
  user_id: string;
  at: string;
  /** paired · client.configured */
  client?: string;
  /** client.configured */
  ok?: boolean;
  reason?: string;
  /** scan.started */
  repo_count?: number;
  /** project.created · project.enriched */
  slug?: string;
  name?: string;
  pitch?: string;
  stack?: string[];
  /** done */
  project_count?: number;
}

const MAX_BACKOFF_MS = 30_000;

export const useOnboardingStore = defineStore("onboarding", () => {
  /** Every frame, in arrival order. The screen renders this as a log. */
  const events = ref<OnboardingEvent[]>([]);
  const connected = ref(false);

  let es: EventSource | null = null;
  let reconnectHandle: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;

  // ── Derived view the setup screen actually renders ──────────────────────

  const paired = computed(() => events.value.some((e) => e.type === "paired"));

  /** One row per MCP client the installer touched, in the order it reported. */
  const clients = computed(() => {
    const seen = new Map<string, { client: string; ok: boolean; reason?: string }>();
    for (const e of events.value) {
      if (e.type === "client.configured" && e.client) {
        seen.set(e.client, { client: e.client, ok: e.ok ?? false, reason: e.reason });
      }
    }
    return [...seen.values()];
  });

  const repoCount = computed(
    () => events.value.find((e) => e.type === "scan.started")?.repo_count ?? null,
  );

  /**
   * Projects in creation order, each flipping to enriched when its second
   * event lands. Keyed by slug so a duplicate frame updates rather than
   * appends — a reconnect can legitimately replay one.
   */
  const projects = computed(() => {
    const byslug = new Map<string, { slug: string; name: string; enriched: boolean; pitch?: string }>();
    for (const e of events.value) {
      if (!e.slug) continue;
      if (e.type === "project.created") {
        const existing = byslug.get(e.slug);
        byslug.set(e.slug, {
          slug: e.slug,
          name: e.name ?? e.slug,
          enriched: existing?.enriched ?? false,
          pitch: existing?.pitch,
        });
      } else if (e.type === "project.enriched") {
        const existing = byslug.get(e.slug);
        byslug.set(e.slug, {
          slug: e.slug,
          name: existing?.name ?? e.name ?? e.slug,
          enriched: true,
          pitch: e.pitch,
        });
      }
    }
    return [...byslug.values()];
  });

  const done = computed(() => events.value.some((e) => e.type === "done"));

  const finalProjectCount = computed(
    () => events.value.find((e) => e.type === "done")?.project_count ?? null,
  );

  // ── Connection ─────────────────────────────────────────────────────────

  function close(): void {
    if (reconnectHandle) {
      clearTimeout(reconnectHandle);
      reconnectHandle = null;
    }
    if (es) {
      es.close();
      es = null;
    }
    connected.value = false;
  }

  function open(): void {
    close();
    attempt += 1;
    // withCredentials so the session cookie rides along — without it the
    // stream 401s on cross-origin previews.
    es = new EventSource("/api/v1/onboarding/stream", { withCredentials: true });

    es.onopen = () => {
      connected.value = true;
      attempt = 0;
    };

    es.onmessage = (ev) => {
      if (!ev.data) return;
      try {
        events.value.push(JSON.parse(ev.data) as OnboardingEvent);
      } catch {
        /* malformed frame — ignore rather than break the log */
      }
    };

    es.onerror = () => {
      connected.value = false;
      // Stop retrying once the run is over: a `done` frame means the stream
      // has nothing left to say, and hammering it would be pure noise.
      if (done.value) {
        close();
        return;
      }
      if (es) {
        es.close();
        es = null;
      }
      const delay = Math.min(MAX_BACKOFF_MS, 1_000 * 2 ** Math.min(attempt, 5));
      reconnectHandle = setTimeout(open, delay);
    };
  }

  /** Drop accumulated frames — for restarting onboarding without a reload. */
  function reset(): void {
    close();
    events.value = [];
    attempt = 0;
  }

  return {
    events,
    connected,
    paired,
    clients,
    repoCount,
    projects,
    done,
    finalProjectCount,
    open,
    close,
    reset,
  };
});
