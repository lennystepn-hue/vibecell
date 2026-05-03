/**
 * Shared admin-action lifecycle. Every admin write follows the same
 * shape: collect a fresh TOTP code → fire the request with the
 * X-Vibecell-2FA header → on success, notify the caller so it can
 * refetch the affected resource.
 *
 * Form state for action-specific inputs (days, reason, coupon fields,
 * etc.) lives ON THIS COMPOSABLE so AdminActionModal can render the
 * right inputs based on the active kind without per-page teleport
 * gymnastics. Pages pre-fill defaults via `open(...)` — the modal
 * reads + writes the same reactive object, the URL builder reads
 * from it at request time.
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
  /** Free-form context the modal renders — user email, coupon id, etc. */
  targetLabel?: string | null;
}

interface ExtendTrialForm { days: number }
interface CompDaysForm { days: number; reason: string }
interface CancelSubForm { reason: string; immediate: boolean }
interface ToggleAdminForm { is_admin: boolean }
interface CreateCouponForm {
  code: string;
  name: string;
  percent_off: number;
  amount_off_cents: number;
  duration: "once" | "repeating" | "forever";
  duration_in_months: number;
  max_redemptions: number;
  use_amount: boolean;
}

interface ActionState {
  kind: AdminActionKind;
  config: AdminActionConfig | null;
  code: string;
  running: boolean;
  error: string | null;
  // Action-specific forms — modal renders the relevant slice based
  // on `kind`. Defaults seeded at composable init; overrides flow
  // through `open(...)` per-action.
  extendTrial: ExtendTrialForm;
  compDays: CompDaysForm;
  cancelSub: CancelSubForm;
  toggleAdmin: ToggleAdminForm;
  createCoupon: CreateCouponForm;
}

const FRESH_FORMS = (): Pick<
  ActionState,
  "extendTrial" | "compDays" | "cancelSub" | "toggleAdmin" | "createCoupon"
> => ({
  extendTrial: { days: 14 },
  compDays: { days: 30, reason: "" },
  cancelSub: { reason: "", immediate: false },
  toggleAdmin: { is_admin: false },
  createCoupon: {
    code: "",
    name: "",
    percent_off: 20,
    amount_off_cents: 0,
    duration: "once",
    duration_in_months: 1,
    max_redemptions: 100,
    use_amount: false,
  },
});

const state = reactive<ActionState>({
  kind: null,
  config: null,
  code: "",
  running: false,
  error: null,
  ...FRESH_FORMS(),
});

const completionCallbacks = new Set<() => void | Promise<void>>();

/**
 * Build the request body for the active action from the composable's
 * form state. Returns undefined for pure DELETE / no-body actions.
 */
function buildBody(): unknown {
  switch (state.kind) {
    case "extend-trial":
      return { days: state.extendTrial.days };
    case "comp-days":
      return {
        days: state.compDays.days,
        reason: state.compDays.reason || "comped",
      };
    case "cancel-sub":
      return {
        reason: state.cancelSub.reason || "admin cancel",
        immediate: state.cancelSub.immediate,
      };
    case "toggle-admin":
      return { is_admin: state.toggleAdmin.is_admin };
    case "create-coupon": {
      const c = state.createCoupon;
      return {
        code: c.code.trim(),
        name: c.name.trim() || null,
        percent_off: c.use_amount ? null : c.percent_off,
        amount_off_cents: c.use_amount ? c.amount_off_cents : null,
        duration: c.duration,
        duration_in_months: c.duration === "repeating" ? c.duration_in_months : null,
        max_redemptions: c.max_redemptions || null,
      };
    }
    case "mark-verified":
    case "delete-user":
    case "delete-coupon":
    case null:
      return undefined;
  }
}

/**
 * Per-action form pre-fills. Pages pass these via `open(..., prefill)`
 * to set values like "current is_admin" or "default trial days".
 */
export interface AdminActionPrefill {
  extendTrial?: Partial<ExtendTrialForm>;
  compDays?: Partial<CompDaysForm>;
  cancelSub?: Partial<CancelSubForm>;
  toggleAdmin?: Partial<ToggleAdminForm>;
  createCoupon?: Partial<CreateCouponForm>;
}

export function useAdminActions() {
  function open(config: AdminActionConfig, prefill?: AdminActionPrefill): void {
    state.kind = config.kind;
    state.config = config;
    state.code = "";
    state.error = null;
    state.running = false;
    // Reset all forms to defaults, then layer the prefill on top.
    Object.assign(state, FRESH_FORMS());
    if (prefill?.extendTrial) Object.assign(state.extendTrial, prefill.extendTrial);
    if (prefill?.compDays)    Object.assign(state.compDays,    prefill.compDays);
    if (prefill?.cancelSub)   Object.assign(state.cancelSub,   prefill.cancelSub);
    if (prefill?.toggleAdmin) Object.assign(state.toggleAdmin, prefill.toggleAdmin);
    if (prefill?.createCoupon) Object.assign(state.createCoupon, prefill.createCoupon);
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
      const headers: Record<string, string> = { "X-Vibecell-2FA": state.code };
      const body = buildBody();
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
      for (const cb of completionCallbacks) {
        try { await cb(); } catch { /* swallow */ }
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

  return { state, codeValid, open, close, run, onActionCompleted };
}
