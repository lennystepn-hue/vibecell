import { onBeforeUnmount, ref, watch } from "vue";

// ---------------------------------------------------------------------------
// Event-bus fan-out
// ---------------------------------------------------------------------------
//
// ProjectDetail installs one SSE subscription per page load via
// installProjectLive(). Card components that want to self-refresh subscribe
// via onProjectLiveEvent(types, handler). This keeps the wiring flat: cards
// never have to know about EventSource or the SSE stream — they just say
// "refetch when a session is created" and it happens.

const _bus = new EventTarget();

export function onProjectLiveEvent(
  types: string | string[],
  handler: (event: ProjectEvent) => void,
): void {
  const list = Array.isArray(types) ? types : [types];
  const listener = (e: Event) => handler((e as CustomEvent<ProjectEvent>).detail);
  for (const t of list) _bus.addEventListener(t, listener);
  onBeforeUnmount(() => {
    for (const t of list) _bus.removeEventListener(t, listener);
  });
}

function _broadcast(event: ProjectEvent): void {
  _bus.dispatchEvent(new CustomEvent(event.type, { detail: event }));
  _bus.dispatchEvent(new CustomEvent("*", { detail: event }));
}

/**
 * Subscribe to the server-sent project event stream for the given slug.
 *
 * Every mutation on the server (session, decision, idea, note, ship, secret,
 * screenshot, todo, …) publishes a small event that lands here within
 * milliseconds. Pass an `onEvent` handler and route to the affected store's
 * refetch based on `event.type` — the dashboard stays live without polling.
 *
 * Reconnects with exponential-ish backoff on stream drop so moving between
 * pages doesn't leak EventSource instances. Automatically tears down when
 * the composable's owner unmounts.
 */
export interface ProjectEvent {
  type: string;
  project_id: string;
  at: string;
  [key: string]: unknown;
}

export function useProjectLive(
  getSlug: () => string | undefined,
  onEvent: (event: ProjectEvent) => void,
): { connected: ReturnType<typeof ref<boolean>>; close: () => void } {
  const connected = ref(false);
  let es: EventSource | null = null;
  let reconnectHandle: ReturnType<typeof setTimeout> | null = null;
  let attempt = 0;

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

  function open(slug: string): void {
    close();
    attempt += 1;
    // EventSource sends cookies by default when withCredentials=true; without
    // it session auth would break on cross-origin previews.
    es = new EventSource(`/api/v1/projects/${slug}/events/stream`, {
      withCredentials: true,
    });
    es.onopen = () => {
      connected.value = true;
      attempt = 0;
    };
    es.onmessage = (ev) => {
      if (!ev.data) return;
      try {
        const data = JSON.parse(ev.data) as ProjectEvent;
        onEvent(data);
        _broadcast(data);  // fan out to card listeners via onProjectLiveEvent
      } catch {
        /* malformed frame — ignore */
      }
    };
    es.onerror = () => {
      connected.value = false;
      // EventSource auto-reconnects, but if the server returns 4xx it won't.
      // Force an explicit reopen with backoff to handle that case.
      if (es) {
        es.close();
        es = null;
      }
      const delay = Math.min(30_000, 1_000 * 2 ** Math.min(attempt, 5));
      reconnectHandle = setTimeout(() => {
        const s = getSlug();
        if (s) open(s);
      }, delay);
    };
  }

  watch(
    getSlug,
    (slug) => {
      if (!slug) {
        close();
        return;
      }
      open(slug);
    },
    { immediate: true },
  );

  onBeforeUnmount(() => close());

  return { connected, close };
}
