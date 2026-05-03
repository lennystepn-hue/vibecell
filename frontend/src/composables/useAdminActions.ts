/**
 * Shared admin-action lifecycle. Every admin write follows the same
 * shape: collect a fresh TOTP code → fire the request with the
 * X-Vibecell-2FA header → on success, notify the caller so it can
 * refetch the affected resource.
 *
 * Centralised here so each admin page (Users / Coupons / Audit /
 * Settings) doesn't duplicate ~80 lines of identical 2FA-prompt
 * scaffolding. Pages just call openAction(...) and provide the URL +
 * body builder; the shared modal in AdminLayout reads from this state.
 */
import { computed, reactive } from "vue";

export type AdminActionKind =
  | "extend-trial"
  | "comp-days"
  | "cancel-sub"
  | "mark-verified"
  | "toggle-admin"
  | "delete-user"
  | "create-coupon"
  | "delete-coupon"
  | null;

export interface AdminActionConfig {
  kind: NonNullable<AdminActionKind>;
  url: string;
  method?: "POST" | "DELETE";
  body?: () => unknown;
  // Free-form context the modal can render — the user's email if it's
  // a per-user action, the coupon id if it's a per-coupon action, etc.
  targetLabel?: string | null;
}

interface ActionState {
  kind: AdminActionKind;
  config: AdminActionConfig | null;
  code: string;
  running: boolean;
  error: string | null;
}

// Module-scoped singleton. Pages provide/inject would also work but
// every admin page wants the same instance; a module-scope reactive
// is simpler and survives navigation between admin routes.
const state = reactive<ActionState>({
  kind: null,
  config: null,
  code: "",
  running: false,
  error: null,
});

// onCompleted callbacks fire after a successful run. Pages register
// theirs in onMounted and unregister in onBeforeUnmount; the modal
// fires every registered callback so the active page can refetch.
const completionCallbacks = new Set<() => void | Promise<void>>();

export function useAdminActions() {
  function open(config: AdminActionConfig): void {
    state.kind = config.kind;
    state.config = config;
    state.code = "";
    state.error = null;
    state.running = false;
  }

  function close(): void {
    state.kind = null;
    state.config = null;
    state.code = "";
    state.error = null;
    state.running = false;
  }

  async function run(): Promise<boolean> {
    if (!state.config || !/^\d{6}$/.test(state.code)) return false;
    state.running = true;
    state.error = null;
    try {
      const headers: Record<string, string> = {
        "X-Vibecell-2FA": state.code,
      };
      const body = state.config.body?.();
      if (body !== undefined) headers["Content-Type"] = "application/json";

      const res = await fetch(state.config.url, {
        method: state.config.method ?? "POST",
        credentials: "include",
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const blob = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(blob.detail || `HTTP ${res.status}`);
      }
      // Fire all registered onCompleted callbacks so page-level state
      // refreshes (the page that opened the action gets to refetch).
      for (const cb of completionCallbacks) {
        try {
          await cb();
        } catch {
          /* swallow — one bad callback shouldn't block the rest */
        }
      }
      close();
      return true;
    } catch (e) {
      state.error = e instanceof Error ? e.message : "Failed";
      return false;
    } finally {
      state.running = false;
    }
  }

  function onActionCompleted(cb: () => void | Promise<void>): () => void {
    completionCallbacks.add(cb);
    return () => completionCallbacks.delete(cb);
  }

  const codeValid = computed(() => /^\d{6}$/.test(state.code));

  return {
    state,
    codeValid,
    open,
    close,
    run,
    onActionCompleted,
  };
}
