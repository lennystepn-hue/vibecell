<script setup lang="ts">
/**
 * Admin dashboard — production overview + actions.
 *
 * Auth: triple-gated server-side (require_admin → email-allowlist + DB
 * is_admin flag), and the route guard in router/index.ts also checks
 * auth.user.is_admin so non-admins don't even get to load the bundle.
 *
 * Layout (cockpit-density, single accent per surface):
 *   • KPI strip across the top (users / paying / MRR / ARR / projects /
 *     ships / sessions / signups). Polls /overview every 30s.
 *   • Two-column body (md+):
 *       Left  — Users table with search + Trial-extend action
 *       Right — Recent activity feed + Audit log + Coupons
 *   • All write actions trigger an inline 2FA prompt (X-Vibecell-2FA
 *     header) since the backend require_admin_2fa demands a fresh code.
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

interface KPI {
  label: string;
  value: number | string;
  accent?: string | null;
  delta?: string | null;
}
interface Overview {
  kpis: KPI[];
  subs_by_status: Record<string, number>;
  mrr_eur: number;
  arr_eur: number;
  generated_at: string;
}
interface UserRow {
  id: string;
  email: string;
  name: string | null;
  created_at: string | null;
  email_verified_at: string | null;
  is_admin: boolean;
  totp_enabled: boolean;
  workspace_count: number;
  sub_status: string | null;
  sub_trial_ends_at: string | null;
}
interface UsersList { items: UserRow[]; total: number }
interface ActivityRow {
  kind: string;
  at: string;
  title: string;
  detail?: string | null;
  target_id?: string | null;
}
interface CouponRow {
  id: string;
  name: string | null;
  percent_off: number | null;
  amount_off: number | null;
  currency: string | null;
  duration: string;
  duration_in_months: number | null;
  max_redemptions: number | null;
  times_redeemed: number;
  valid: boolean;
}
interface AuditRow {
  id: string;
  actor_user_id: string;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  payload: Record<string, unknown>;
  ip: string | null;
  at: string;
}

const overview = ref<Overview | null>(null);
const users = ref<UsersList | null>(null);
const usersQuery = ref("");
const usersLoading = ref(false);
const activity = ref<ActivityRow[]>([]);
const coupons = ref<CouponRow[]>([]);
const audit = ref<AuditRow[]>([]);
const loadError = ref<string | null>(null);
const overviewHandle = ref<ReturnType<typeof setInterval> | null>(null);

// ── Action modal state ─────────────────────────────────────────────
type ActionKind =
  | "extend-trial"
  | "create-coupon"
  | "delete-coupon"
  | null;
const action = ref<ActionKind>(null);
const action2faCode = ref("");
const actionTarget = ref<string | null>(null);
const actionRunning = ref(false);
const actionError = ref<string | null>(null);

// Coupon-create form
const newCoupon = ref({
  code: "",
  name: "",
  percent_off: 20,
  amount_off_cents: 0,
  duration: "once" as "once" | "repeating" | "forever",
  duration_in_months: 1,
  max_redemptions: 100,
  use_amount: false,
});

// Trial-extend form
const trialDays = ref(14);

// ── Loaders ───────────────────────────────────────────────────────

async function loadOverview() {
  try {
    const r = await fetch("/api/v1/admin/overview", { credentials: "include" });
    if (!r.ok) {
      if (r.status === 403 || r.status === 401) {
        loadError.value = "admin access denied";
      }
      return;
    }
    overview.value = (await r.json()) as Overview;
  } catch {
    /* silent */
  }
}

async function loadUsers() {
  usersLoading.value = true;
  try {
    const q = usersQuery.value.trim();
    const url = `/api/v1/admin/users?limit=50${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    const r = await fetch(url, { credentials: "include" });
    if (r.ok) users.value = (await r.json()) as UsersList;
  } finally {
    usersLoading.value = false;
  }
}

async function loadActivity() {
  const r = await fetch("/api/v1/admin/recent-activity?limit=30", {
    credentials: "include",
  });
  if (r.ok) activity.value = ((await r.json()) as { items: ActivityRow[] }).items;
}

async function loadCoupons() {
  try {
    const r = await fetch("/api/v1/admin/coupons", { credentials: "include" });
    if (r.ok) coupons.value = ((await r.json()) as { items: CouponRow[] }).items;
  } catch {
    coupons.value = [];
  }
}

async function loadAudit() {
  const r = await fetch("/api/v1/admin/audit-log?limit=30", { credentials: "include" });
  if (r.ok) audit.value = ((await r.json()) as { items: AuditRow[] }).items;
}

async function loadAll() {
  await Promise.all([
    loadOverview(),
    loadUsers(),
    loadActivity(),
    loadCoupons(),
    loadAudit(),
  ]);
}

onMounted(async () => {
  await loadAll();
  // Refresh KPIs every 30s so the dashboard tracks live state without
  // hammering the DB. Other tables (users, audit) don't auto-refresh —
  // user pulls them via search / explicit reload.
  overviewHandle.value = setInterval(loadOverview, 30000);
});
onBeforeUnmount(() => {
  if (overviewHandle.value) clearInterval(overviewHandle.value);
});

// ── Actions ───────────────────────────────────────────────────────

function openExtendTrial(user: UserRow) {
  action.value = "extend-trial";
  actionTarget.value = user.id;
  trialDays.value = 14;
  action2faCode.value = "";
  actionError.value = null;
}

function openCreateCoupon() {
  action.value = "create-coupon";
  actionTarget.value = null;
  action2faCode.value = "";
  actionError.value = null;
  newCoupon.value = {
    code: "",
    name: "",
    percent_off: 20,
    amount_off_cents: 0,
    duration: "once",
    duration_in_months: 1,
    max_redemptions: 100,
    use_amount: false,
  };
}

function openDeleteCoupon(coupon: CouponRow) {
  action.value = "delete-coupon";
  actionTarget.value = coupon.id;
  action2faCode.value = "";
  actionError.value = null;
}

function closeAction() {
  action.value = null;
  actionTarget.value = null;
  action2faCode.value = "";
  actionRunning.value = false;
  actionError.value = null;
}

async function runAction() {
  if (!action.value || !/^\d{6}$/.test(action2faCode.value)) return;
  actionRunning.value = true;
  actionError.value = null;
  try {
    let url = "";
    let method = "POST";
    let body: unknown = null;
    if (action.value === "extend-trial") {
      url = `/api/v1/admin/users/${actionTarget.value}/extend-trial`;
      body = { days: trialDays.value };
    } else if (action.value === "create-coupon") {
      url = "/api/v1/admin/coupons";
      const c = newCoupon.value;
      body = {
        code: c.code.trim(),
        name: c.name.trim() || null,
        percent_off: c.use_amount ? null : c.percent_off,
        amount_off_cents: c.use_amount ? c.amount_off_cents : null,
        duration: c.duration,
        duration_in_months: c.duration === "repeating" ? c.duration_in_months : null,
        max_redemptions: c.max_redemptions,
      };
    } else if (action.value === "delete-coupon") {
      url = `/api/v1/admin/coupons/${actionTarget.value}`;
      method = "DELETE";
    }
    const headers: Record<string, string> = {
      "X-Vibecell-2FA": action2faCode.value,
    };
    if (body) headers["Content-Type"] = "application/json";

    const r = await fetch(url, {
      method,
      credentials: "include",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) {
      const blob = (await r.json().catch(() => ({}))) as { detail?: string };
      throw new Error(blob.detail || `HTTP ${r.status}`);
    }
    toast.push("Action completed", "success");
    closeAction();
    await Promise.all([loadOverview(), loadUsers(), loadCoupons(), loadAudit()]);
  } catch (e) {
    actionError.value = e instanceof Error ? e.message : "Failed";
  } finally {
    actionRunning.value = false;
  }
}

const codeValid = computed(() => /^\d{6}$/.test(action2faCode.value));

function fmtRel(iso: string): string {
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

function statusColor(s: string | null): string {
  if (!s) return "var(--fg-subtle)";
  if (s === "active") return "var(--signal-green)";
  if (s === "trialing") return "var(--signal-blue)";
  if (s === "past_due") return "var(--signal-amber, #f59e0b)";
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
</script>

<template>
  <div class="min-h-[calc(100vh-44px)]">
    <div class="max-w-[1400px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
      <!-- Header -->
      <header class="flex items-baseline justify-between mb-8 flex-wrap gap-4">
        <div>
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">
            Admin · production overview
          </p>
          <h1 class="text-display text-fg-primary tracking-tight">Dashboard</h1>
        </div>
        <p
          v-if="overview"
          class="font-mono text-[11px] text-fg-subtle"
        >// auto-refresh 30s · last {{ fmtRel(overview.generated_at) }}</p>
      </header>

      <!-- 403 fallback -->
      <div
        v-if="loadError"
        class="glass rounded-lg p-6 mb-6"
        :style="{ background: 'var(--signal-red-bg)', border: '1px solid var(--signal-red)' }"
      >
        <p class="text-section text-fg-primary mb-1">Access denied</p>
        <p class="text-small text-fg-muted">
          You don't have admin access. If you should — your email must be in
          <code>HANGAR_ADMIN_EMAILS</code> and your <code>users.is_admin</code>
          flag must be true.
        </p>
      </div>

      <template v-else>
        <!-- KPI strip -->
        <section v-if="overview" class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 mb-8">
          <div
            v-for="k in overview.kpis"
            :key="k.label"
            class="glass rounded-lg p-3"
          >
            <p class="mono-label opacity-60 mb-1 text-[9px]">{{ k.label }}</p>
            <p
              class="font-mono font-semibold tabular-nums"
              style="font-size: 22px; letter-spacing: -0.03em"
              :style="kpiAccentStyle(k.accent)"
            >{{ k.value }}</p>
            <p
              v-if="k.delta"
              class="text-[10px] font-mono mt-0.5"
              :style="{ color: 'var(--signal-green)' }"
            >{{ k.delta }}</p>
          </div>
        </section>

        <!-- Subs-by-status pill row -->
        <section v-if="overview" class="flex flex-wrap items-center gap-2 mb-6">
          <span class="mono-label">// subs by status</span>
          <span
            v-for="(count, status) in overview.subs_by_status"
            :key="status"
            class="font-mono text-small px-2 py-1 rounded-md tabular-nums"
            :style="{
              background: 'rgba(20,33,50,0.4)',
              color: statusColor(status),
              border: '1px solid var(--border)',
            }"
          >{{ status }} · {{ count }}</span>
        </section>

        <!-- Two-column body -->
        <div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
          <!-- Left: Users + Coupons -->
          <div class="space-y-6 min-w-0">
            <!-- Users -->
            <section class="glass rounded-lg p-5">
              <header class="flex items-center justify-between mb-4 gap-3 flex-wrap">
                <h3 class="mono-label text-fg-muted">
                  //users <span class="opacity-60" v-if="users">({{ users.total }})</span>
                </h3>
                <input
                  v-model="usersQuery"
                  type="text"
                  placeholder="search by email…"
                  class="h-8 px-2 rounded-md text-small font-mono bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle w-full sm:w-60"
                  @keydown.enter="loadUsers"
                />
              </header>
              <div v-if="usersLoading && !users" class="text-small text-fg-subtle font-mono">loading…</div>
              <div v-else-if="users && users.items.length === 0" class="text-small text-fg-muted">
                No users match.
              </div>
              <div v-else-if="users" class="overflow-x-auto -mx-2 px-2">
                <table class="w-full text-small font-mono">
                  <thead>
                    <tr class="text-left text-fg-subtle border-b border-border-subtle">
                      <th class="py-2 pr-3">email</th>
                      <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">status</th>
                      <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">trial ends</th>
                      <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">2fa</th>
                      <th class="py-2 pr-3 text-[10px] uppercase tracking-wider">since</th>
                      <th class="py-2"></th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="u in users.items"
                      :key="u.id"
                      class="border-b border-border-subtle last:border-b-0 hover:bg-white/[0.03]"
                    >
                      <td class="py-2 pr-3 truncate max-w-[200px]">
                        <span :title="u.email">{{ u.email }}</span>
                        <span
                          v-if="u.is_admin"
                          class="ml-1.5 text-[9px] px-1 py-0.5 rounded-sm"
                          :style="{ background: 'var(--signal-green-bg)', color: 'var(--signal-green)' }"
                        >ADMIN</span>
                      </td>
                      <td class="py-2 pr-3">
                        <span :style="{ color: statusColor(u.sub_status) }">{{ u.sub_status ?? "—" }}</span>
                      </td>
                      <td class="py-2 pr-3 text-fg-subtle">
                        {{ u.sub_trial_ends_at ? new Date(u.sub_trial_ends_at).toLocaleDateString() : "—" }}
                      </td>
                      <td class="py-2 pr-3">
                        <span
                          :style="u.totp_enabled
                            ? { color: 'var(--signal-green)' }
                            : { color: 'var(--fg-subtle)' }"
                        >{{ u.totp_enabled ? "✓" : "—" }}</span>
                      </td>
                      <td class="py-2 pr-3 text-fg-subtle">
                        {{ u.created_at ? fmtRel(u.created_at) : "—" }}
                      </td>
                      <td class="py-2 text-right">
                        <button
                          type="button"
                          class="text-[11px] text-fg-muted hover:text-fg-body transition-colors"
                          @click="openExtendTrial(u)"
                        >+trial</button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>

            <!-- Coupons -->
            <section class="glass rounded-lg p-5">
              <header class="flex items-center justify-between mb-4">
                <h3 class="mono-label text-fg-muted">//coupons <span class="opacity-60">({{ coupons.length }})</span></h3>
                <button
                  type="button"
                  class="font-mono text-small text-fg-muted hover:text-fg-body transition-colors"
                  @click="openCreateCoupon"
                >+ new coupon</button>
              </header>
              <div v-if="coupons.length === 0" class="text-small text-fg-muted">
                No Stripe coupons defined.
              </div>
              <ul v-else class="space-y-1">
                <li
                  v-for="c in coupons"
                  :key="c.id"
                  class="flex items-center gap-3 py-2 border-b border-border-subtle last:border-b-0"
                >
                  <span
                    class="font-mono text-small"
                    :style="c.valid ? { color: 'var(--fg-primary)' } : { color: 'var(--fg-subtle)', textDecoration: 'line-through' }"
                  >{{ c.id }}</span>
                  <span class="font-mono text-small text-fg-muted">
                    {{ c.percent_off ? `${c.percent_off}% off` : c.amount_off ? `€${(c.amount_off / 100).toFixed(2)} off` : "" }}
                  </span>
                  <span class="font-mono text-[10px] text-fg-subtle">{{ c.duration }}</span>
                  <span class="ml-auto font-mono text-[10px] text-fg-subtle tabular-nums">
                    {{ c.times_redeemed }}{{ c.max_redemptions ? ` / ${c.max_redemptions}` : "" }}
                  </span>
                  <button
                    type="button"
                    class="text-[11px] text-fg-subtle hover:text-signal-red transition-colors"
                    @click="openDeleteCoupon(c)"
                  >delete</button>
                </li>
              </ul>
            </section>
          </div>

          <!-- Right: Activity + Audit -->
          <div class="space-y-6 min-w-0">
            <section class="glass rounded-lg p-5">
              <h3 class="mono-label text-fg-muted mb-4">//recent activity</h3>
              <ul v-if="activity.length" class="space-y-2">
                <li
                  v-for="ev in activity"
                  :key="ev.kind + ':' + (ev.target_id ?? '') + ev.at"
                  class="flex items-start gap-3 text-small"
                >
                  <span class="font-mono text-fg-subtle shrink-0 w-3 text-center">{{ activityIcon(ev.kind) }}</span>
                  <div class="min-w-0 flex-1">
                    <p class="text-fg-body truncate">{{ ev.title }}</p>
                    <p v-if="ev.detail" class="text-fg-muted text-[11px] truncate">{{ ev.detail }}</p>
                    <p class="text-fg-subtle text-[10px] font-mono mt-0.5">{{ fmtRel(ev.at) }}</p>
                  </div>
                </li>
              </ul>
              <p v-else class="text-small text-fg-muted">No recent activity.</p>
            </section>

            <section class="glass rounded-lg p-5">
              <h3 class="mono-label text-fg-muted mb-4">//admin audit log</h3>
              <ul v-if="audit.length" class="space-y-2">
                <li
                  v-for="row in audit"
                  :key="row.id"
                  class="text-small font-mono text-fg-body border-b border-border-subtle pb-2 last:border-b-0"
                >
                  <span class="text-signal-amber">{{ row.action }}</span>
                  <span v-if="row.target_id" class="text-fg-subtle"> · {{ row.target_id }}</span>
                  <p class="text-[10px] text-fg-subtle mt-0.5">
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

    <!-- ── ACTION MODAL ───────────────────────────────────────────── -->
    <div
      v-if="action"
      class="fixed inset-0 z-50 flex items-center justify-center px-4"
      style="background: rgba(7,11,16,0.65); backdrop-filter: blur(4px)"
      @click.self="closeAction"
    >
      <div
        class="glass rounded-xl w-full max-w-[460px] p-6 space-y-4"
        style="background: var(--bg-chrome)"
      >
        <header class="flex items-center justify-between">
          <h2 class="text-section text-fg-primary font-semibold">
            {{ action === "extend-trial" ? "Extend trial"
              : action === "create-coupon" ? "Create coupon"
              : "Delete coupon" }}
          </h2>
          <button
            type="button"
            class="text-fg-subtle hover:text-fg-body"
            @click="closeAction"
          >✕</button>
        </header>

        <!-- Trial-extend body -->
        <div v-if="action === 'extend-trial'" class="space-y-3">
          <p class="text-small text-fg-muted">
            Push the user's <code>trial_ends_at</code> further into the
            future. DB-only change; doesn't sync back to Stripe.
          </p>
          <label class="block">
            <span class="mono-label">// days to add</span>
            <input
              v-model.number="trialDays"
              type="number"
              min="1"
              max="180"
              class="mt-1 h-10 w-32 px-3 rounded-md font-mono text-body bg-bg-surface border border-border text-fg-primary"
            />
          </label>
        </div>

        <!-- Coupon-create body -->
        <div v-else-if="action === 'create-coupon'" class="space-y-3">
          <label class="block">
            <span class="mono-label">// code (becomes the Stripe ID)</span>
            <input
              v-model="newCoupon.code"
              type="text"
              maxlength="40"
              placeholder="LAUNCH69"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono text-body bg-bg-surface border border-border text-fg-primary uppercase"
            />
          </label>
          <label class="block">
            <span class="mono-label">// display name (optional)</span>
            <input
              v-model="newCoupon.name"
              type="text"
              maxlength="40"
              placeholder="Vibecell Launch"
              class="mt-1 h-10 w-full px-3 rounded-md font-sans text-body bg-bg-surface border border-border text-fg-primary"
            />
          </label>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-2 text-small text-fg-body">
              <input v-model="newCoupon.use_amount" type="checkbox" class="accent-signal-green" />
              fixed amount
            </label>
            <label v-if="!newCoupon.use_amount" class="block flex-1">
              <span class="mono-label">// percent off</span>
              <input
                v-model.number="newCoupon.percent_off"
                type="number" min="1" max="100"
                class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
              />
            </label>
            <label v-else class="block flex-1">
              <span class="mono-label">// amount cents (eur)</span>
              <input
                v-model.number="newCoupon.amount_off_cents"
                type="number" min="50" max="100000"
                class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
              />
            </label>
          </div>
          <label class="block">
            <span class="mono-label">// duration</span>
            <select
              v-model="newCoupon.duration"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono text-body bg-bg-surface border border-border text-fg-primary"
            >
              <option value="once">once</option>
              <option value="repeating">repeating</option>
              <option value="forever">forever</option>
            </select>
          </label>
          <label v-if="newCoupon.duration === 'repeating'" class="block">
            <span class="mono-label">// duration in months</span>
            <input
              v-model.number="newCoupon.duration_in_months"
              type="number" min="1" max="24"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
            />
          </label>
          <label class="block">
            <span class="mono-label">// max redemptions (0 = unlimited)</span>
            <input
              v-model.number="newCoupon.max_redemptions"
              type="number" min="0" max="10000"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
            />
          </label>
        </div>

        <!-- Delete-coupon body -->
        <div v-else-if="action === 'delete-coupon'" class="space-y-3">
          <p class="text-small text-fg-muted">
            Permanently delete coupon
            <code class="font-mono text-fg-body">{{ actionTarget }}</code>
            from Stripe. Existing subscriptions that have it applied keep
            it; only new applications are blocked.
          </p>
        </div>

        <!-- 2FA prompt — common to all admin write actions -->
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
          <PrimaryButton
            :loading="actionRunning"
            :disabled="!codeValid || actionRunning"
            @click="runAction"
          >
            {{ action === "delete-coupon" ? "Delete" : "Confirm" }}
          </PrimaryButton>
        </div>
      </div>
    </div>
  </div>
</template>
