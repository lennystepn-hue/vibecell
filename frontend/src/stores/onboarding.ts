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

export interface PairingCode {
  code: string;
  expires_in: number;
  install_sh: string;
  install_ps1: string;
}

const MAX_BACKOFF_MS = 30_000;

/**
 * Reissue at 80% of the code's life. Far enough ahead that a slow round trip
 * can't leave a dead line on screen, late enough that an idle tab isn't
 * minting codes every minute.
 */
const REISSUE_AT = 0.8;

export const useOnboardingStore = defineStore("onboarding", () => {
  /** Every frame, in arrival order. The screen renders this as a log. */
  const events = ref<OnboardingEvent[]>([]);
  const connected = ref(false);

  /** The live one-liner shown on screen. Null until the first mint lands. */
  const pairing = ref<PairingCode | null>(null);

  let es: EventSource | null = null;
  let reconnectHandle: ReturnType<typeof setTimeout> | null = null;
  let reissueHandle: ReturnType<typeof setTimeout> | null = null;
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

  // ── Pairing code ───────────────────────────────────────────────────────

  /**
   * Mint a one-time pairing code and keep it alive.
   *
   * Codes expire after 10 minutes, and a user who reads the page, makes
   * coffee and then opens a terminal would otherwise paste a dead line and
   * get an error that looks like the product is broken. So we re-mint ahead
   * of expiry, silently — the line on screen is never dead.
   *
   * Stops once the machine is paired: the line has done its job, and a tab
   * left open overnight should not keep minting credentials.
   */
  async function mintCode(): Promise<void> {
    if (reissueHandle) {
      clearTimeout(reissueHandle);
      reissueHandle = null;
    }
    try {
      const res = await fetch("/api/v1/onboarding/code", {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) return;
      const next = (await res.json()) as PairingCode;
      pairing.value = next;
      if (!paired.value) {
        reissueHandle = setTimeout(
          () => void mintCode(),
          next.expires_in * 1000 * REISSUE_AT,
        );
      }
    } catch {
      /* offline or logged out — the screen keeps the last code it had */
    }
  }

  // ── Connection ─────────────────────────────────────────────────────────

  function close(): void {
    if (reconnectHandle) {
      clearTimeout(reconnectHandle);
      reconnectHandle = null;
    }
    if (reissueHandle) {
      clearTimeout(reissueHandle);
      reissueHandle = null;
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
    pairing.value = null;
    attempt = 0;
  }

  return {
    events,
    connected,
    pairing,
    mintCode,
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
