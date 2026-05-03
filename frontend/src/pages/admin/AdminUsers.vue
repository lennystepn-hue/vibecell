<script setup lang="ts">
/**
 * /admin/users — full users surface with search, detail panel, and
 * the per-user power-action grid. Action triggers go through
 * useAdminActions which prompts for a fresh TOTP and fires via
 * the AdminActionModal mounted in AdminLayout.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

import { useAdminActions, type AdminActionConfig } from "@/composables/useAdminActions";

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

const adminActions = useAdminActions();

const users = ref<{ items: UserRow[]; total: number } | null>(null);
const usersQuery = ref("");
const usersLoading = ref(false);

const detailOpen = ref(false);
const detailLoading = ref(false);
const detail = ref<UserDetail | null>(null);

async function loadUsers() {
  usersLoading.value = true;
  try {
    const q = usersQuery.value.trim();
    const url = `/api/v1/admin/users?limit=100${q ? `&q=${encodeURIComponent(q)}` : ""}`;
    const r = await fetch(url, { credentials: "include" });
    if (r.ok) users.value = (await r.json()) as { items: UserRow[]; total: number };
  } finally {
    usersLoading.value = false;
  }
}

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

onMounted(loadUsers);

// After any successful admin action, refetch the table + detail panel.
let unregister: (() => void) | null = null;
onMounted(() => {
  unregister = adminActions.onActionCompleted(async () => {
    await loadUsers();
    if (detail.value) await openDetail(detail.value.user.id);
  });
});
onBeforeUnmount(() => unregister?.());

// ── Action openers ────────────────────────────────────────────────

const trialDays = ref(14);
const compDays = ref(30);
const compReason = ref("");
const cancelReason = ref("");
const cancelImmediate = ref(false);

function openExtendTrial(u: UserRow) {
  trialDays.value = 14;
  const cfg: AdminActionConfig = {
    kind: "extend-trial",
    url: `/api/v1/admin/users/${u.id}/extend-trial`,
    body: () => ({ days: trialDays.value }),
    targetLabel: u.email,
  };
  adminActions.open(cfg);
}
function openCompDays(u: UserRow) {
  compDays.value = 30;
  compReason.value = "";
  adminActions.open({
    kind: "comp-days",
    url: `/api/v1/admin/users/${u.id}/comp-days`,
    body: () => ({ days: compDays.value, reason: compReason.value || "comped" }),
    targetLabel: u.email,
  });
}
function openCancelSub(u: UserRow) {
  cancelReason.value = "";
  cancelImmediate.value = false;
  adminActions.open({
    kind: "cancel-sub",
    url: `/api/v1/admin/users/${u.id}/cancel-subscription`,
    body: () => ({ reason: cancelReason.value || "admin cancel", immediate: cancelImmediate.value }),
    targetLabel: u.email,
  });
}
function openMarkVerified(u: UserRow) {
  adminActions.open({
    kind: "mark-verified",
    url: `/api/v1/admin/users/${u.id}/mark-email-verified`,
    targetLabel: u.email,
  });
}
function openToggleAdmin(u: UserRow) {
  adminActions.open({
    kind: "toggle-admin",
    url: `/api/v1/admin/users/${u.id}/toggle-admin`,
    body: () => ({ is_admin: !u.is_admin }),
    targetLabel: u.email,
  });
}
function openDeleteUser(u: UserRow) {
  adminActions.open({
    kind: "delete-user",
    url: `/api/v1/admin/users/${u.id}`,
    method: "DELETE",
    targetLabel: u.email,
  });
}

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
</script>

<template>
  <div class="max-w-[1400px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="flex items-baseline justify-between mb-6 flex-wrap gap-4">
      <div>
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · users</p>
        <h1 class="text-display text-fg-primary tracking-tight">Users</h1>
      </div>
      <input
        v-model="usersQuery"
        type="text"
        placeholder="search by email…"
        class="h-9 px-3 rounded-md text-small font-mono bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle w-full sm:w-80"
        @keydown.enter="loadUsers"
      />
    </header>

    <section class="glass rounded-lg p-1">
      <div v-if="usersLoading && !users" class="text-small text-fg-subtle font-mono p-4">loading…</div>
      <div v-else-if="users && users.items.length === 0" class="text-small text-fg-muted p-4">No users match.</div>
      <div v-else-if="users" class="overflow-x-auto">
        <table class="w-full text-small font-mono">
          <thead>
            <tr class="text-left text-fg-subtle border-b border-border-subtle">
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">email</th>
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">status</th>
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">trial</th>
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">verified</th>
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">2fa</th>
              <th class="py-2 px-3 text-[10px] uppercase tracking-wider">since</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in users.items"
              :key="u.id"
              class="border-b border-border-subtle last:border-b-0 hover:bg-white/[0.04] cursor-pointer"
              @click="openDetail(u.id)"
            >
              <td class="py-2 px-3 truncate max-w-[300px]">
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
              <td class="py-2 px-3">
                <span :style="{ color: statusColor(u.effective_status) }">{{ u.effective_status ?? "—" }}</span>
              </td>
              <td class="py-2 px-3 text-fg-subtle text-[11px]">{{ u.sub_trial_ends_at ? fmtDate(u.sub_trial_ends_at) : "—" }}</td>
              <td class="py-2 px-3">
                <span :style="u.email_verified_at ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">
                  {{ u.email_verified_at ? "✓" : "—" }}
                </span>
              </td>
              <td class="py-2 px-3">
                <span :style="u.totp_enabled ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">
                  {{ u.totp_enabled ? "✓" : "—" }}
                </span>
              </td>
              <td class="py-2 px-3 text-fg-subtle text-[11px]">{{ u.created_at ? fmtRel(u.created_at) : "—" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- Detail panel — slides in from right -->
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
                <h2 class="text-section text-fg-primary truncate" :title="detail?.user.email">{{ detail?.user.email ?? "—" }}</h2>
                <p class="font-mono text-[10px] text-fg-subtle mt-1 truncate">{{ detail?.user.id }}</p>
              </div>
              <button type="button" class="text-fg-subtle hover:text-fg-body shrink-0" @click="closeDetail">✕</button>
            </header>

            <div v-if="detailLoading" class="text-small text-fg-subtle font-mono">loading…</div>

            <template v-else-if="detail">
              <!-- Identity grid -->
              <div class="grid grid-cols-2 gap-3 text-small">
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">status</p>
                  <p class="font-mono mt-0.5" :style="{ color: statusColor(detail.user.effective_status) }">{{ detail.user.effective_status ?? "—" }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">trial ends</p>
                  <p class="font-mono mt-0.5">{{ fmtDate(detail.user.sub_trial_ends_at) }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">verified</p>
                  <p class="font-mono mt-0.5">{{ detail.user.email_verified_at ? fmtDate(detail.user.email_verified_at) : "—" }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">2FA</p>
                  <p class="font-mono mt-0.5" :style="detail.user.totp_enabled ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">{{ detail.user.totp_enabled ? "enabled" : "—" }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">stripe</p>
                  <p class="font-mono mt-0.5">{{ detail.user.has_stripe_subscription ? "linked" : "—" }}</p>
                </div>
                <div>
                  <p class="font-mono text-[9px] opacity-50 uppercase tracking-[0.12em]">admin</p>
                  <p class="font-mono mt-0.5" :style="detail.user.is_admin ? { color: 'var(--signal-green)' } : { color: 'var(--fg-subtle)' }">{{ detail.user.is_admin ? "yes" : "no" }}</p>
                </div>
              </div>

              <!-- Activity stats -->
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
                <p class="font-mono text-[10px] text-fg-subtle mt-3">last session · {{ fmtRel(detail.last_session_at) }}</p>
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

              <!-- Power actions -->
              <div class="border-t border-border pt-4">
                <p class="mono-label mb-3">// admin actions</p>
                <div class="grid grid-cols-2 gap-2">
                  <button type="button" class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors" @click="openExtendTrial(detail.user)">+ trial days</button>
                  <button type="button" class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors" @click="openCompDays(detail.user)">comp days</button>
                  <button type="button" class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors" :disabled="!!detail.user.email_verified_at" @click="openMarkVerified(detail.user)">mark verified</button>
                  <button type="button" class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface text-fg-body hover:bg-bg-surface-hi transition-colors" @click="openToggleAdmin(detail.user)">{{ detail.user.is_admin ? "demote admin" : "promote admin" }}</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono border border-border bg-bg-surface hover:bg-bg-surface-hi transition-colors col-span-2"
                    :style="{ color: 'var(--signal-amber, #f59e0b)' }"
                    @click="openCancelSub(detail.user)"
                  >cancel subscription</button>
                  <button
                    type="button"
                    class="h-9 px-3 rounded-md text-small font-mono col-span-2 transition-colors"
                    :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)', border: '1px solid var(--signal-red)' }"
                    @click="openDeleteUser(detail.user)"
                  >delete account (GDPR)</button>
                </div>
              </div>
            </template>
          </div>
        </aside>
      </div>
    </transition>
  </div>
</template>
