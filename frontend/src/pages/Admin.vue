<script setup lang="ts">
/**
 * Admin dashboard — the cockpit.
 *
 * Layout (impeccable cockpit-density):
 *   ┌──────────────────────────────────────────────────────────────────┐
 *   │  Header: //admin · production console · last-refresh badge      │
 *   ├──────────────────────────────────────────────────────────────────┤
 *   │  Hero KPI grid — 8 dense tiles, signal-coloured by accent       │
 *   ├──────────────────────────────────────────────────────────────────┤
 *   │  Active-now strip + subs-by-status pills                         │
 *   ├─────────────┬──────────────────────────────────┬─────────────────┤
 *   │ system      │  Users table (search, click row │ Recent activity │
 *   │ health      │   for detail panel, inline      │                  │
 *   │             │   actions)                       │ Audit log       │
 *   │ Coupons     │                                  │                  │
 *   └─────────────┴──────────────────────────────────┴─────────────────┘
 *
 * Auth: triple-gated server-side. Frontend route + sidebar gate are
 * UX layers — server's require_admin is the actual security boundary.
 *
 * Every write action prompts for a fresh TOTP code (X-Vibecell-2FA
 * header). Verifications are not cached — physical access to the
 * authenticator device is required for every admin write.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

interface KPI { label: string; value: number | string; accent?: string | null; delta?: string | null }
interface Overview {
  kpis: KPI[];
  subs_by_status: Record<string, number>;
  mrr_eur: number; arr_eur: number;
  generated_at: string;
}
interface Usage {
  dau: number; wau: number; mau: number; active_now: number;
  sessions_today: number; ships_today: number;
}
interface UserRow {
  id: string; email: string; name: string | null;
  created_at: string | null; email_verified_at: string | null;
  is_admin: boolean; totp_enabled: boolean;
  workspace_count: number;
  sub_status: string | null;
  effective_status: string | null;
  sub_trial_ends_at: string | null;
  sub_trial_email_stage: string | null;
  has_stripe_subscription: boolean;
}
interface UserDetail {
  user: UserRow;
  workspaces: { id: string; slug: string; name: string; plan: string }[];
  project_count: number;
  session_count: number;
  ship_count: number;
  decision_count: number;
  last_session_at: string | null;
}
interface ActivityRow { kind: string; at: string; title: string; detail?: string | null; target_id?: string | null }
interface CouponRow {
  id: string; name: string | null; percent_off: number | null; amount_off: number | null;
  currency: string | null; duration: string; duration_in_months: number | null;
  max_redemptions: number | null; times_redeemed: number; valid: boolean;
}
interface AuditRow {
  id: string; actor_user_id: string; actor_email: string | null;
  action: string; target_type: string | null; target_id: string | null;
  payload: Record<string, unknown>; ip: string | null; at: string;
}
interface HealthRow { label: string; value: string; accent?: string | null }
interface SystemHealth { rows: HealthRow[]; generated_at: string }

const overview = ref<Overview | null>(null);
const usage = ref<Usage | null>(null);
const health = ref<SystemHealth | null>(null);
const users = ref<{ items: UserRow[]; total: number } | null>(null);
const usersQuery = ref("");
const usersLoading = ref(false);
const activity = ref<ActivityRow[]>([]);
const coupons = ref<CouponRow[]>([]);
const audit = ref<AuditRow[]>([]);
const loadError = ref<string | null>(null);
const refreshHandle = ref<ReturnType<typeof setInterval> | null>(null);

// ── User detail panel ─────────────────────────────────────────────
const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref<UserDetail | null>(null);

async function openDetail(userId: string) {
  detailOpen.value = true;
  detailLoading.value = true;
  detail.value = null;
  try {
    const r = await fetch(`/api/v1/admin/users/${userId}`, { credentials: "include" });
    if (r.ok) detail.value = (await r.json()) as UserDetail;
  } finally {
    detailLoading.value = false;
  }
}

function closeDetail() {
  detailOpen.value = false;
  detail.value = null;
}

// ── Action modal ──────────────────────────────────────────────────
type ActionKind =
  | "extend-trial"
  | "comp-days"
  | "cancel-sub"
  | "mark-verified"
  | "toggle-admin"
  | "delete-user"
  | "create-coupon"
  | "delete-coupon"
  | null;

const action = ref<ActionKind>(null);
const action2faCode = ref("");
const actionTarget = ref<string | null>(null);
const actionTargetEmail = ref<string | null>(null);
const actionRunning = ref(false);
const actionError = ref<string | null>(null);

const actionForm = ref<Record<string, unknown>>({});
const newCoupon = ref({
  code: "", name: "", percent_off: 20, amount_off_cents: 0,
  duration: "once" as "once" | "repeating" | "forever",
  duration_in_months: 1, max_redemptions: 100, use_amount: false,
});
const trialDays = ref(14);
const compDays = ref(30);
const cancelReason = ref("");
const cancelImmediate = ref(false);
const compReason = ref("");

function openAction(kind: NonNullable<ActionKind>, target: UserRow | CouponRow | null) {
  action.value = kind;
  action2faCode.value = "";
  actionError.value = null;
  if (target && "email" in target) {
    actionTarget.value = target.id;
    actionTargetEmail.value = target.email;
  } else if (target && "id" in target) {
    actionTarget.value = target.id;
    actionTargetEmail.value = null;
  } else {
    actionTarget.value = null;
    actionTargetEmail.value = null;
  }
  if (kind === "extend-trial") trialDays.value = 14;
  if (kind === "comp-days") {
    compDays.value = 30;
    compReason.value = "";
  }
  if (kind === "cancel-sub") {
    cancelReason.value = "";
    cancelImmediate.value = false;
  }
  if (kind === "create-coupon") {
    newCoupon.value = {
      code: "", name: "", percent_off: 20, amount_off_cents: 0,
      duration: "once", duration_in_months: 1, max_redemptions: 100,
      use_amount: false,
    };
  }
  if (kind === "toggle-admin") {
    actionForm.value = { is_admin: !(target as UserRow | null)?.is_admin };
  }
}

function closeAction() {
  action.value = null;
  actionTarget.value = null;
  actionTargetEmail.value = null;
  action2faCode.value = "";
  actionRunning.value = false;
  actionError.value = null;
  actionForm.value = {};
}

async function runAction() {
  if (!action.value || !/^\d{6}$/.test(action2faCode.value)) return;
  actionRunning.value = true;
  actionError.value = null;
  try {
    let url = "";
    let method = "POST";
    let body: unknown = null;
    switch (action.value) {
      case "extend-trial":
        url = `/api/v1/admin/users/${actionTarget.value}/extend-trial`;
        body = { days: trialDays.value };
        break;
      case "comp-days":
        url = `/api/v1/admin/users/${actionTarget.value}/comp-days`;
        body = { days: compDays.value, reason: compReason.value || "comped" };
        break;
      case "cancel-sub":
        url = `/api/v1/admin/users/${actionTarget.value}/cancel-subscription`;
        body = { reason: cancelReason.value || "admin cancel", immediate: cancelImmediate.value };
        break;
      case "mark-verified":
        url = `/api/v1/admin/users/${actionTarget.value}/mark-email-verified`;
        break;
      case "toggle-admin":
        url = `/api/v1/admin/users/${actionTarget.value}/toggle-admin`;
        body = actionForm.value;
        break;
      case "delete-user":
        url = `/api/v1/admin/users/${actionTarget.value}`;
        method = "DELETE";
        break;
      case "create-coupon": {
        url = "/api/v1/admin/coupons";
        const c = newCoupon.value;
        body = {
          code: c.code.trim(),
          name: c.name.trim() || null,
          percent_off: c.use_amount ? null : c.percent_off,
          amount_off_cents: c.use_amount ? c.amount_off_cents : null,
          duration: c.duration,
          duration_in_months: c.duration === "repeating" ? c.duration_in_months : null,
          max_redemptions: c.max_redemptions || null,
        };
        break;
      }
      case "delete-coupon":
        url = `/api/v1/admin/coupons/${actionTarget.value}`;
        method = "DELETE";
        break;
    }
    const headers: Record<string, string> = { "X-Vibecell-2FA": action2faCode.value };
    if (body) headers["Content-Type"] = "application/json";
    const r = await fetch(url, {
      method, credentials: "include", headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) {
      const blob = (await r.json().catch(() => ({}))) as { detail?: string };
      throw new Error(blob.detail || `HTTP ${r.status}`);
    }
    toast.push("Action completed", "success");
    if (action.value === "delete-user") {
      closeDetail();
    } else if (detail.value && detail.value.user.id === actionTarget.value) {
      // Refresh detail panel if it was open for this user
      const stillId = actionTarget.value;
      closeAction();
      if (stillId) await openDetail(stillId);
    }
    closeAction();
    await loadAll();
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : "Failed";
  } finally {
    actionRunning.value = false;
  }
}

const codeValid = computed(() => /^\d{6}$/.test(action2faCode.value));

// ── Loaders ───────────────────────────────────────────────────────

async function loadOverview() {
  try {
    const r = await fetch("/api/v1/admin/overview", { credentials: "include" });
    if (!r.ok) {
      if (r.status === 403 || r.status === 401) loadError.value = "admin access denied";
      return;
    }
    overview.value = (await r.json()) as Overview;
  } catch { /* silent */ }
}

async function loadUsage() {
  const r = await fetch("/api/v1/admin/usage-metrics", { credentials: "include" });
  if (r.ok) usage.value = (await r.json()) as Usage;
}

async function loadHealth() {
  const r = await fetch("/api/v1/admin/system-health", { credentials: "include" });
  if (r.ok) health.value = (await r.json()) as SystemHealth;
}

async function loadUsers() {
  usersLoading.value = true;
  try {
    const q = usersQuery.value.trim();
    const url = `/api/v1/admin/users?limit=50${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    const r = await fetch(url, { credentials: "include" });
    if (r.ok) users.value = (await r.json()) as { items: UserRow[]; total: number };
  } finally {
    usersLoading.value = false;
  }
}

async function loadActivity() {
  const r = await fetch("/api/v1/admin/recent-activity?limit=30", { credentials: "include" });
  if (r.ok) activity.value = ((await r.json()) as { items: ActivityRow[] }).items;
}

async function loadCoupons() {
  try {
    const r = await fetch("/api/v1/admin/coupons", { credentials: "include" });
    if (r.ok) coupons.value = ((await r.json()) as { items: CouponRow[] }).items;
  } catch { coupons.value = []; }
}

async function loadAudit() {
  const r = await fetch("/api/v1/admin/audit-log?limit=30", { credentials: "include" });
  if (r.ok) audit.value = ((await r.json()) as { items: AuditRow[] }).items;
}

async function loadAll() {
  await Promise.all([loadOverview(), loadUsage(), loadHealth(), loadUsers(), loadActivity(), loadCoupons(), loadAudit()]);
}

onMounted(async () => {
  await loadAll();
  refreshHandle.value = setInterval(() => { void loadOverview(); void loadUsage(); }, 30000);
});
onBeforeUnmount(() => {
  if (refreshHandle.value) clearInterval(refreshHandle.value);
});

// ── Render helpers ────────────────────────────────────────────────

function fmtRel(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().slice(0, 10);
}

function statusColor(s: string | null): string {
  if (!s) return "var(--fg-subtle)";
  if (s === "active") return "var(--signal-green)";
  if (s === "trialing") return "var(--signal-blue, #8ab4ff)";
  if (s === "past_due" || s === "expired_trial") return "var(--signal-amber, #f59e0b)";
  if (s === "canceled" || s === "unpaid") return "var(--signal-red)";
  return "var(--fg-subtle)";
}

function activityIcon(kind: string): string {
  if (kind === "signup") return "◌";
  if (kind === "ship") return "↑";
  if (kind === "decision") return "◇";
  if (kind === "stripe_event") return "€";
  return "·";
}

function kpiAccentStyle(accent?: string | null): Record<string, string> {
  if (accent === "green") return { color: "var(--signal-green)" };
  if (accent === "amber") return { color: "var(--signal-amber, #f59e0b)" };
  if (accent === "red") return { color: "var(--signal-red)" };
  return { color: "var(--fg-primary)" };
}

const expiredTrials = computed<UserRow[]>(() =>
  (users.value?.items ?? []).filter((u) => u.effective_status === "expired_trial"),
);
</script>

<template>
  <div class="min-h-[calc(100vh-44px)]">
    <div class="max-w-[1500px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
      <!-- ── Header ───────────────────────────────────────────────── -->
      <header class="flex items-baseline justify-between mb-6 flex-wrap gap-4">
        <div>
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">
            // admin · production console
          </p>
          <h1 class="text-display text-fg-primary tracking-tight">Cockpit</h1>
        </div>
        <p
          v-if="overview"
          class="font-mono text-[11px] text-fg-subtle"
        >// auto-refresh 30s · {{ fmtRel(overview.generated_at) }}</p>
      </header>

      <!-- ── 403 fallback ─────────────────────────────────────────── -->
      <div
        v-if="loadError"
        class="glass rounded-lg p-6 mb-6"
        :style="{ background: 'var(--signal-red-bg)', border: '1px solid var(--signal-red)' }"
      >
        <p class="text-section text-fg-primary mb-1">Access denied</p>
        <p class="text-small text-fg-muted">
          You don't have admin access. <code>HANGAR_ADMIN_EMAILS</code> AND
          <code>users.is_admin</code> must both be true. Check the audit log
          for the failed attempt.
        </p>
      </div>

      <template v-else>
        <!-- ── KPI grid (impeccable: numbers louder than words) ──── -->
        <section v-if="overview" class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-6">
          <div
            v-for="k in overview.kpis"
            :key="k.label"
            class="glass rounded-lg p-3"
          >
            <p class="font-mono text-[9px] uppercase tracking-[0.12em] opacity-50 mb-1">{{ k.label }}</p>
            <p
              class="font-mono font-semibold tabular-nums"
              style="font-size: 22px; letter-spacing: -0.03em; line-height: 1"
              :style="kpiAccentStyle(k.accent)"
            >{{ k.value }}</p>
            <p
              v-if="k.delta"
              class="text-[10px] font-mono mt-1"
              :style="{ color: 'var(--signal-green)' }"
            >{{ k.delta }}</p>
          </div>
        </section>

        <!-- ── Active-now strip + subs by status ─────────────────── -->
        <section v-if="usage || overview" class="flex flex-wrap items-center gap-2 mb-6 text-small">
          <template v-if="usage">
            <span class="mono-label opacity-60">// active</span>
            <span class="font-mono px-2 py-1 rounded-md tabular-nums"
                  :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)', color: usage.active_now > 0 ? 'var(--signal-green)' : 'var(--fg-muted)' }">
              now · {{ usage.active_now }}
            </span>
            <span class="font-mono px-2 py-1 rounded-md tabular-nums"
                  :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">
              dau · {{ usage.dau }}
            </span>
            <span class="font-mono px-2 py-1 rounded-md tabular-nums"
                  :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">
              wau · {{ usage.wau }}
            </span>
            <span class="font-mono px-2 py-1 rounded-md tabular-nums"
                  :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">
              mau · {{ usage.mau }}
            </span>
          </template>
          <template v-if="overview">
            <span class="mono-label opacity-60 ml-2">// subs</span>
            <span
              v-for="(count, status) in overview.subs_by_status"
              :key="status"
              class="font-mono px-2 py-1 rounded-md tabular-nums"
              :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)', color: statusColor(status) }"
            >{{ status }} · {{ count }}</span>
          </template>
        </section>

        <!-- ── Expired-trial banner if any ───────────────────────── -->
        <div
          v-if="expiredTrials.length > 0"
          class="glass rounded-lg p-3 mb-6 flex items-center gap-3"
          :style="{ background: 'var(--signal-amber-bg, rgba(245,158,11,0.08))', borderColor: 'rgba(245,158,11,0.3)', borderWidth: '1px' }"
        >
          <span class="font-mono" style="color: var(--signal-amber, #f59e0b)">!</span>
          <p class="text-small text-fg-body">
            <strong>{{ expiredTrials.length }} expired trial{{ expiredTrials.length === 1 ? "" : "s" }}</strong>
            currently in DB as "trialing" — the hourly cron will flip them to past_due. The dashboard
            already shows their effective status.
          </p>
        </div>

        <!-- ── Three-column body ─────────────────────────────────── -->
        <div class="grid grid-cols-1 lg:grid-cols-[260px_1fr_320px] gap-5">
          <!-- LEFT: System health + Coupons -->
          <div class="space-y-5 min-w-0">
            <section class="glass rounded-lg p-4">
              <h3 class="mono-label text-fg-muted mb-3">//system health</h3>
              <div v-if="health" class="space-y-1.5">
                <div
                  v-for="row in health.rows"
                  :key="row.label"
                  class="flex items-center justify-between text-small"
                >
                  <span class="font-mono text-fg-subtle">{{ row.label }}</span>
                  <span
                    class="font-mono tabular-nums truncate ml-2"
                    :style="kpiAccentStyle(row.accent)"
                  >{{ row.value }}</span>
                </div>
              </div>
              <div v-else class="text-small text-fg-subtle font-mono">loading…</div>
            </section>

            <section class="glass rounded-lg p-4">
              <header class="flex items-center justify-between mb-3">
                <h3 class="mono-label text-fg-muted">//coupons <span class="opacity-60">({{ coupons.length }})</span></h3>
                <button
                  type="button"
                  class="font-mono text-[11px] text-fg-muted hover:text-fg-body transition-colors"
                  @click="openAction('create-coupon', null)"
                >+ new</button>
              </header>
              <div v-if="coupons.length === 0" class="text-small text-fg-muted">No Stripe coupons.</div>
              <ul v-else class="space-y-1.5">
                <li
                  v-for="c in coupons"
                  :key="c.id"
                  class="flex items-center gap-2 text-small min-w-0"
                >
                  <span
                    class="font-mono truncate flex-1 min-w-0"
                    :style="c.valid ? { color: 'var(--fg-primary)' } : { color: 'var(--fg-subtle)', textDecoration: 'line-through' }"
                  >{{ c.id }}</span>
                  <span class="font-mono text-fg-subtle text-[10px] tabular-nums shrink-0">
                    {{ c.percent_off ? `${c.percent_off}%` : c.amount_off ? `€${(c.amount_off/100).toFixed(0)}` : "" }}
                  </span>
                  <span class="font-mono text-fg-subtle text-[10px] tabular-nums shrink-0">
                    {{ c.times_redeemed }}{{ c.max_redemptions ? `/${c.max_redemptions}` : "" }}
                  </span>
                  <button
                    type="button"
                    class="text-[11px] text-fg-subtle hover:text-signal-red transition-colors shrink-0"
                    @click="openAction('delete-coupon', c)"
                  >×</button>
                </li>
              </ul>
            </section>
          </div>

          <!-- CENTER: Users table -->
          <section class="glass rounded-lg p-4 min-w-0">
            <header class="flex items-center justify-between mb-3 gap-3 flex-wrap">
              <h3 class="mono-label text-fg-muted">
                //users <span class="opacity-60" v-if="users">({{ users.total }})</span>
              </h3>
              <input
                v-model="usersQuery"
                type="text"
                placeholder="search by email…"
                class="h-8 px-3 rounded-md text-small font-mono bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle w-full sm:w-64"
                @keydown.enter="loadUsers"
              />
            </header>
            <div v-if="usersLoading && !users" class="text-small text-fg-subtle font-mono">loading…</div>
            <div v-else-if="users && users.items.length === 0" class="text-small text-fg-muted">
              No users match.
            </div>
            <div v-else-if="users" class="overflow-x-auto -mx-1 px-1">
              <table class="w-full text-small font-mono">
                <thead>
                  <tr class="text-left text-fg-subtle border-b border-border-subtle">
                    <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">email</th>
                    <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">status</th>
                    <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">trial</th>
                    <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">2fa</th>
                    <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">since</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="u in users.items"
                    :key="u.id"
                    class="border-b border-border-subtle last:border-b-0 hover:bg-white/[0.04] cursor-pointer"
                    @click="openDetail(u.id)"
                  >
                    <td class="py-2 pr-3 truncate max-w-[260px]">
                      <span :title="u.email">{{ u.email }}</span>
                      <span
                        v-if="u.is_admin"
                        class="ml-1.5 text-[9px] px-1 py-0.5 rounded-sm tabular-nums"
                        :style="{ background: 'var(--signal-green-bg)', color: 'var(--signal-green)' }"
                      >ADMIN</span>
                      <span
                        v-if="u.has_stripe_subscription"
                        class="ml-1 text-[9px] px-1 py-0.5 rounded-sm tabular-nums"
                        :style="{ background: 'rgba(99,91,255,0.12)', color: 'rgba(180,170,255,0.85)' }"
                        title="Has Stripe subscription"
                      >S</span>
                    </td>
                    <td class="py-2 pr-3">
                      <span :style="{ color: statusColor(u.effective_status) }">
                        {{ u.effective_status ?? "—" }}
                      </span>
                    </td>
                    <td class="py-2 pr-3 text-fg-subtle text-[11px]">
                      {{ u.sub_trial_ends_at ? fmtDate(u.sub_trial_ends_at) : "—" }}
                    </td>
                    <td class="py-2 pr-3">
                      <span :style="u.totp_enabled ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">
                        {{ u.totp_enabled ? "✓" : "—" }}
                      </span>
                    </td>
                    <td class="py-2 pr-3 text-fg-subtle text-[11px]">
                      {{ u.created_at ? fmtRel(u.created_at) : "—" }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <!-- RIGHT: Activity + Audit -->
          <div class="space-y-5 min-w-0">
            <section class="glass rounded-lg p-4">
              <h3 class="mono-label text-fg-muted mb-3">//recent activity</h3>
              <ul v-if="activity.length" class="space-y-2 max-h-[260px] overflow-y-auto">
                <li
                  v-for="ev in activity"
                  :key="ev.kind + ':' + (ev.target_id ?? '') + ev.at"
                  class="flex items-start gap-2 text-small"
                >
                  <span class="font-mono text-fg-subtle shrink-0 w-3 text-center">{{ activityIcon(ev.kind) }}</span>
                  <div class="min-w-0 flex-1">
                    <p class="text-fg-body truncate text-[12px]">{{ ev.title }}</p>
                    <p v-if="ev.detail" class="text-fg-muted text-[10px] truncate">{{ ev.detail }}</p>
                    <p class="text-fg-subtle text-[9px] font-mono mt-0.5">{{ fmtRel(ev.at) }}</p>
                  </div>
                </li>
              </ul>
              <p v-else class="text-small text-fg-muted">No recent activity.</p>
            </section>

            <section class="glass rounded-lg p-4">
              <h3 class="mono-label text-fg-muted mb-3">//admin audit</h3>
              <ul v-if="audit.length" class="space-y-2 max-h-[260px] overflow-y-auto">
                <li
                  v-for="row in audit"
                  :key="row.id"
                  class="font-mono text-[11px] text-fg-body border-b border-border-subtle pb-1.5 last:border-b-0"
                >
                  <span :style="{ color: 'var(--signal-amber, #f59e0b)' }">{{ row.action }}</span>
                  <span v-if="row.target_id" class="text-fg-subtle"> · {{ row.target_id.slice(0, 12) }}…</span>
                  <p class="text-[9px] text-fg-subtle mt-0.5 truncate">
                    {{ row.actor_email ?? row.actor_user_id }} · {{ row.ip ?? "?" }} · {{ fmtRel(row.at) }}
                  </p>
                </li>
              </ul>
              <p v-else class="text-small text-fg-muted">No actions yet.</p>
            </section>
          </div>
        </div>
      </template>
    </div>

    <!-- ── USER DETAIL PANEL ────────────────────────────────────── -->
    <transition
      enter-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="detailOpen"
        class="fixed inset-0 z-40 flex justify-end"
        style="background: rgba(7,11,16,0.55); backdrop-filter: blur(2px)"
        @click.self="closeDetail"
      >
        <aside
          class="h-full w-full sm:w-[520px] overflow-y-auto chrome border-l shadow-2xl"
          @click.stop
        >
          <div class="p-6 space-y-5">
            <header class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <p class="font-mono text-[10px] uppercase tracking-[0.12em] text-fg-subtle mb-1">// user</p>
                <h2 class="text-section text-fg-primary truncate" :title="detail?.user.email">
                  {{ detail?.user.email ?? "—" }}
                </h2>
                <p class="font-mono text-[10px] text-fg-subtle mt-1 truncate">{{ detail?.user.id }}</p>
              </div>
              <button
                type="button"
                class="text-fg-subtle hover:text-fg-body shrink-0"
                @click="closeDetail"
              >✕</button>
            </header>

            <div v-if="detailLoading" class="text-small text-fg-subtle font-mono">loading…</div>

            <template v-else-if="detail">
              <!-- Identity grid -->
              <div class="grid grid-cols-2 gap-3 text-small">
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">status</p>
                  <p class="font-mono mt-0.5" :style="{ color: statusColor(detail.user.effective_status) }">
                    {{ detail.user.effective_status ?? "—" }}
                  </p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">trial ends</p>
                  <p class="font-mono mt-0.5">{{ fmtDate(detail.user.sub_trial_ends_at) }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">verified</p>
                  <p class="font-mono mt-0.5">
                    {{ detail.user.email_verified_at ? fmtDate(detail.user.email_verified_at) : "—" }}
                  </p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">2FA</p>
                  <p class="font-mono mt-0.5" :style="detail.user.totp_enabled ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">
                    {{ detail.user.totp_enabled ? "enabled" : "—" }}
                  </p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">stripe</p>
                  <p class="font-mono mt-0.5">{{ detail.user.has_stripe_subscription ? "linked" : "—" }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">admin</p>
                  <p class="font-mono mt-0.5" :style="detail.user.is_admin ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">
                    {{ detail.user.is_admin ? "yes" : "no" }}
                  </p>
                </div>
              </div>

              <!-- Stats -->
              <div class="border-t border-border pt-4">
                <p class="mono-label mb-2">// activity</p>
                <div class="grid grid-cols-4 gap-3">
                  <div>
                    <p class="font-mono text-[9px] opacity-50 uppercase">workspaces</p>
                    <p class="font-mono text-section tabular-nums">{{ detail.user.workspace_count }}</p>
                  </div>
                  <div>
                    <p class="font-mono text-[9px] opacity-50 uppercase">projects</p>
                    <p class="font-mono text-section tabular-nums">{{ detail.project_count }}</p>
                  </div>
                  <div>
                    <p class="font-mono text-[9px] opacity-50 uppercase">sessions</p>
                    <p class="font-mono text-section tabular-nums">{{ detail.session_count }}</p>
                  </div>
                  <div>
                    <p class="font-mono text-[9px] opacity-50 uppercase">ships</p>
                    <p class="font-mono text-section tabular-nums">{{ detail.ship_count }}</p>
                  </div>
                </div>
                <p class="font-mono text-[10px] text-fg-subtle mt-3">
                  last session · {{ fmtRel(detail.last_session_at) }}
                </p>
              </div>

              <!-- Workspaces -->
              <div v-if="detail.workspaces.length" class="border-t border-border pt-4">
                <p class="mono-label mb-2">// workspaces</p>
                <ul class="space-y-1">
                  <li
                    v-for="w in detail.workspaces"
                    :key="w.id"
                    class="font-mono text-small text-fg-body flex items-center gap-2"
                  >
                    <span class="text-fg-subtle">{{ w.slug }}</span>
                    <span class="text-fg-muted">·</span>
                    <span>{{ w.name }}</span>
                  </li>
                </ul>
              </div>

              <!-- Power-action grid -->
              <div class="border-t border-border pt-4">
                <p class="mono-label mb-3">// admin actions</p>
                <div class="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
                    @click="openAction('extend-trial', detail.user)"
                  >+ trial days</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
                    @click="openAction('comp-days', detail.user)"
                  >comp days</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
                    :disabled="!!detail.user.email_verified_at"
                    @click="openAction('mark-verified', detail.user)"
                  >mark verified</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors"
                    @click="openAction('toggle-admin', detail.user)"
                  >{{ detail.user.is_admin ? "demote admin" : "promote admin" }}</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors col-span-2"
                    :style="{ color: 'var(--signal-amber, #f59e0b)' }"
                    @click="openAction('cancel-sub', detail.user)"
                  >cancel subscription</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono col-span-2 transition-colors"
                    :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)', border: '1px solid var(--signal-red)' }"
                    @click="openAction('delete-user', detail.user)"
                  >delete account (GDPR)</button>
                </div>
              </div>
            </template>
          </div>
        </aside>
      </div>
    </transition>

    <!-- ── ACTION MODAL ─────────────────────────────────────────── -->
    <div
      v-if="action"
      class="fixed inset-0 z-50 flex items-center justify-center px-4"
      style="background: rgba(7,11,16,0.7); backdrop-filter: blur(4px)"
      @click.self="closeAction"
    >
      <div class="glass rounded-xl w-full max-w-[460px] p-6 space-y-4" style="background: var(--bg-chrome)">
        <header class="flex items-center justify-between">
          <h2 class="text-section text-fg-primary font-semibold">
            {{ {
              "extend-trial": "Extend trial",
              "comp-days": "Comp days",
              "cancel-sub": "Cancel subscription",
              "mark-verified": "Mark email verified",
              "toggle-admin": "Toggle admin",
              "delete-user": "Delete account (GDPR)",
              "create-coupon": "Create coupon",
              "delete-coupon": "Delete coupon",
            }[action!] }}
          </h2>
          <button type="button" class="text-fg-subtle hover:text-fg-body" @click="closeAction">✕</button>
        </header>

        <p
          v-if="actionTargetEmail && action !== 'create-coupon'"
          class="text-small text-fg-muted"
        >Target: <span class="font-mono text-fg-body">{{ actionTargetEmail }}</span></p>

        <!-- Per-action body -->
        <div v-if="action === 'extend-trial'" class="space-y-2">
          <p class="text-small text-fg-muted">Push <code>trial_ends_at</code> forward + reset email-stage so warning emails fire again. Syncs to Stripe.</p>
          <label class="block">
            <span class="mono-label">// days</span>
            <input v-model.number="trialDays" type="number" min="1" max="180" class="mt-1 h-10 w-32 px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
          </label>
        </div>
        <div v-else-if="action === 'comp-days'" class="space-y-3">
          <p class="text-small text-fg-muted">Comp the user N days of paid-equivalent service. Sets status active/trialing + extends end-date. Syncs to Stripe.</p>
          <label class="block">
            <span class="mono-label">// days</span>
            <input v-model.number="compDays" type="number" min="1" max="365" class="mt-1 h-10 w-32 px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
          </label>
          <label class="block">
            <span class="mono-label">// reason (audit log)</span>
            <input v-model="compReason" type="text" maxlength="200" placeholder="support refund / launch promo / …" class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary" />
          </label>
        </div>
        <div v-else-if="action === 'cancel-sub'" class="space-y-3">
          <p class="text-small text-fg-muted">DB always updates; Stripe sync triggered if linked.</p>
          <label class="flex items-center gap-2 text-small text-fg-body">
            <input v-model="cancelImmediate" type="checkbox" class="accent-signal-red" />
            cancel immediately (default: cancel at period end)
          </label>
          <label class="block">
            <span class="mono-label">// reason</span>
            <input v-model="cancelReason" type="text" maxlength="200" placeholder="user request / fraud / …" class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary" />
          </label>
        </div>
        <div v-else-if="action === 'mark-verified'" class="text-small text-fg-muted">
          Stamps <code>email_verified_at = now()</code>. Use this when magic-link bounced but you've otherwise verified the user out-of-band.
        </div>
        <div v-else-if="action === 'toggle-admin'" class="text-small text-fg-muted">
          Sets <code>users.is_admin = {{ actionForm.is_admin ? "true" : "false" }}</code>.
          The <code>HANGAR_ADMIN_EMAILS</code> env list is the OTHER required gate — both must agree before admin access is granted.
        </div>
        <div v-else-if="action === 'delete-user'" class="space-y-2">
          <p class="text-small" :style="{ color: 'var(--signal-red)' }">
            <strong>Irreversible.</strong> Deletes all user data per GDPR Art. 17. Workspaces, projects, sessions, ships, decisions, secrets — all purged in one transaction. Stripe subscription is canceled best-effort.
          </p>
          <p class="text-[11px] text-fg-subtle font-mono">
            Audit log entry survives the purge so the deletion itself is forensically traceable.
          </p>
        </div>
        <div v-else-if="action === 'create-coupon'" class="space-y-3">
          <label class="block">
            <span class="mono-label">// code (becomes the Stripe ID)</span>
            <input v-model="newCoupon.code" type="text" maxlength="40" placeholder="LAUNCH69" class="mt-1 h-10 w-full px-3 rounded-md font-mono uppercase bg-bg-surface border border-border text-fg-primary" />
          </label>
          <label class="block">
            <span class="mono-label">// display name (optional)</span>
            <input v-model="newCoupon.name" type="text" maxlength="40" placeholder="Vibecell Launch" class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary" />
          </label>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-small text-fg-body">
              <input v-model="newCoupon.use_amount" type="checkbox" class="accent-signal-green" /> fixed amount
            </label>
            <label v-if="!newCoupon.use_amount" class="flex-1 block">
              <span class="mono-label">// percent off</span>
              <input v-model.number="newCoupon.percent_off" type="number" min="1" max="100" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
            </label>
            <label v-else class="flex-1 block">
              <span class="mono-label">// cents (eur)</span>
              <input v-model.number="newCoupon.amount_off_cents" type="number" min="50" max="100000" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
            </label>
          </div>
          <label class="block">
            <span class="mono-label">// duration</span>
            <select v-model="newCoupon.duration" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary">
              <option value="once">once</option>
              <option value="repeating">repeating</option>
              <option value="forever">forever</option>
            </select>
          </label>
          <label v-if="newCoupon.duration === 'repeating'" class="block">
            <span class="mono-label">// duration in months</span>
            <input v-model.number="newCoupon.duration_in_months" type="number" min="1" max="24" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
          </label>
          <label class="block">
            <span class="mono-label">// max redemptions (0 = unlimited)</span>
            <input v-model.number="newCoupon.max_redemptions" type="number" min="0" max="10000" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
          </label>
        </div>
        <div v-else-if="action === 'delete-coupon'" class="text-small text-fg-muted">
          Permanently delete coupon <code class="font-mono text-fg-body">{{ actionTarget }}</code> from Stripe. Existing subs that have it stay applied; only new applications are blocked.
        </div>

        <!-- 2FA prompt — every admin write requires a fresh code. -->
        <div class="space-y-2 pt-3 border-t border-border">
          <MonoLabel>2FA code (TOTP)</MonoLabel>
          <input
            v-model="action2faCode"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
            placeholder="000000"
            class="h-10 w-32 px-3 rounded-md font-mono text-section tracking-[0.2em] text-center bg-bg-surface border border-border text-fg-primary"
            @keydown.enter="codeValid && runAction()"
          />
        </div>

        <p
          v-if="actionError"
          class="text-small p-3 rounded-md"
          :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)', border: '1px solid var(--signal-red)' }"
        >{{ actionError }}</p>

        <div class="flex items-center justify-end gap-3 pt-1">
          <button
            type="button"
            class="text-small text-fg-muted hover:text-fg-body transition-colors"
            :disabled="actionRunning"
            @click="closeAction"
          >cancel</button>
          <PrimaryButton :loading="actionRunning" :disabled="!codeValid || actionRunning" @click="runAction">
            {{ ({
              "delete-user": "Delete account",
              "delete-coupon": "Delete coupon",
              "cancel-sub": "Cancel sub",
            } as Record<string, string>)[action!] ?? "Confirm" }}
          </PrimaryButton>
        </div>
      </div>
    </div>
  </div>
</template>
