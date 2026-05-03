<script setup lang="ts">
/**
 * /admin/overview — production cockpit landing.
 *
 * Hero KPI grid + active-now strip + subs-by-status pills.
 * Right rail: system health snapshot + recent activity feed.
 * No actions on this page — pure read; navigation goes elsewhere.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

interface KPI { label: string; value: number | string; accent?: string | null; delta?: string | null }
interface Overview {
  kpis: KPI[];
  subs_by_status: Record<string, number>;
  mrr_eur: number;
  arr_eur: number;
  generated_at: string;
}
interface Usage {
  dau: number; wau: number; mau: number; active_now: number;
  sessions_today: number; ships_today: number;
}
interface ActivityRow {
  kind: string; at: string; title: string;
  detail?: string | null; target_id?: string | null;
}
interface HealthRow { label: string; value: string; accent?: string | null }
interface SystemHealth { rows: HealthRow[]; generated_at: string }

const overview = ref<Overview | null>(null);
const usage = ref<Usage | null>(null);
const health = ref<SystemHealth | null>(null);
const activity = ref<ActivityRow[]>([]);
const loadError = ref<string | null>(null);
const refreshHandle = ref<ReturnType<typeof setInterval> | null>(null);

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
async function loadActivity() {
  const r = await fetch("/api/v1/admin/recent-activity?limit=20", { credentials: "include" });
  if (r.ok) activity.value = ((await r.json()) as { items: ActivityRow[] }).items;
}

onMounted(async () => {
  await Promise.all([loadOverview(), loadUsage(), loadHealth(), loadActivity()]);
  refreshHandle.value = setInterval(() => {
    void loadOverview();
    void loadUsage();
    void loadHealth();
  }, 30000);
});
onBeforeUnmount(() => {
  if (refreshHandle.value) clearInterval(refreshHandle.value);
});

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
function statusColor(s: string): string {
  if (s === "active") return "var(--signal-green)";
  if (s === "trialing") return "var(--signal-blue, #8ab4ff)";
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
  <div class="max-w-[1400px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="flex items-baseline justify-between mb-6 flex-wrap gap-4">
      <div>
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · overview</p>
        <h1 class="text-display text-fg-primary tracking-tight">Cockpit</h1>
      </div>
      <p
        v-if="overview"
        class="font-mono text-[11px] text-fg-subtle"
      >// auto-refresh 30s · {{ fmtRel(overview.generated_at) }}</p>
    </header>

    <div
      v-if="loadError"
      class="glass rounded-lg p-6 mb-6"
      :style="{ background: 'var(--signal-red-bg)', border: '1px solid var(--signal-red)' }"
    >
      <p class="text-section text-fg-primary mb-1">Access denied</p>
      <p class="text-small text-fg-muted">
        HANGAR_ADMIN_EMAILS AND users.is_admin must both be true.
      </p>
    </div>

    <template v-else>
      <!-- KPI grid -->
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

      <!-- Active strip -->
      <section v-if="usage || overview" class="flex flex-wrap items-center gap-2 mb-6 text-small">
        <template v-if="usage">
          <span class="mono-label opacity-60">// active</span>
          <span class="font-mono px-2 py-1 rounded-md tabular-nums"
                :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)', color: usage.active_now > 0 ? 'var(--signal-green)' : 'var(--fg-muted)' }">
            now · {{ usage.active_now }}
          </span>
          <span class="font-mono px-2 py-1 rounded-md tabular-nums" :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">dau · {{ usage.dau }}</span>
          <span class="font-mono px-2 py-1 rounded-md tabular-nums" :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">wau · {{ usage.wau }}</span>
          <span class="font-mono px-2 py-1 rounded-md tabular-nums" :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)' }">mau · {{ usage.mau }}</span>
        </template>
        <template v-if="overview">
          <span class="mono-label opacity-60 ml-2">// subs</span>
          <span
            v-for="(count, status) in overview.subs_by_status"
            :key="status"
            class="font-mono px-2 py-1 rounded-md tabular-nums"
            :style="{ background: 'rgba(20,33,50,0.4)', border: '1px solid var(--border)', color: statusColor(String(status)) }"
          >{{ status }} · {{ count }}</span>
        </template>
      </section>

      <!-- Two columns: system health (left) + activity (right) -->
      <div class="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">
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
          <h3 class="mono-label text-fg-muted mb-3">//recent activity</h3>
          <ul v-if="activity.length" class="space-y-2 max-h-[420px] overflow-y-auto">
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
      </div>
    </template>
  </div>
</template>
