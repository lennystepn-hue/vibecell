<script setup lang="ts">
/**
 * /admin/coupons — Stripe coupon CRUD via the admin API.
 * Create + delete go through the shared 2FA modal.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";

import { useAdminActions } from "@/composables/useAdminActions";

interface CouponRow {
  id: string; name: string | null; percent_off: number | null; amount_off: number | null;
  currency: string | null; duration: string; duration_in_months: number | null;
  max_redemptions: number | null; times_redeemed: number; valid: boolean;
}

const adminActions = useAdminActions();
const coupons = ref<CouponRow[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const r = await fetch("/api/v1/admin/coupons", { credentials: "include" });
    if (r.ok) coupons.value = ((await r.json()) as { items: CouponRow[] }).items;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

let unregister: (() => void) | null = null;
onMounted(() => { unregister = adminActions.onActionCompleted(load); });
onBeforeUnmount(() => unregister?.());

function openCreate() {
  adminActions.open({
    kind: "create-coupon",
    url: "/api/v1/admin/coupons",
  });
}
function openDelete(c: CouponRow) {
  adminActions.open({
    kind: "delete-coupon",
    url: `/api/v1/admin/coupons/${c.id}`,
    method: "DELETE",
    targetLabel: c.id,
  });
}
</script>

<template>
  <div class="max-w-[900px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="flex items-baseline justify-between mb-6 gap-4 flex-wrap">
      <div>
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · coupons</p>
        <h1 class="text-display text-fg-primary tracking-tight">Coupons</h1>
        <p class="text-body text-fg-muted mt-1">Stripe coupons. Code = Stripe ID, must be unique account-wide.</p>
      </div>
      <button
        type="button"
        class="h-10 px-4 rounded-md font-mono text-small bg-signal-green hover:opacity-90 transition-opacity"
        :style="{ color: 'var(--bg-body-to)' }"
        @click="openCreate"
      >+ new coupon</button>
    </header>

    <!-- Existing coupons (create form lives in the action modal — keeps
         all admin writes behind the same 2FA gate). -->
    <section class="glass rounded-lg p-1">
      <div v-if="loading && !coupons.length" class="p-4 text-small text-fg-subtle font-mono">loading…</div>
      <div v-else-if="!coupons.length" class="p-4 text-small text-fg-muted">No Stripe coupons defined.</div>
      <table v-else class="w-full text-small font-mono">
        <thead>
          <tr class="text-left text-fg-subtle border-b border-border-subtle">
            <th class="py-2 px-3 text-[10px] uppercase tracking-wider">id</th>
            <th class="py-2 px-3 text-[10px] uppercase tracking-wider">discount</th>
            <th class="py-2 px-3 text-[10px] uppercase tracking-wider">duration</th>
            <th class="py-2 px-3 text-[10px] uppercase tracking-wider">redeemed</th>
            <th class="py-2 px-3 text-[10px] uppercase tracking-wider">valid</th>
            <th class="py-2 px-3"></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in coupons"
            :key="c.id"
            class="border-b border-border-subtle last:border-b-0"
          >
            <td class="py-2 px-3" :style="c.valid ? {} : { color: 'var(--fg-subtle)', textDecoration: 'line-through' }">{{ c.id }}</td>
            <td class="py-2 px-3 text-fg-body">
              {{ c.percent_off ? `${c.percent_off}% off` : c.amount_off ? `€${(c.amount_off/100).toFixed(2)} off` : "—" }}
            </td>
            <td class="py-2 px-3 text-fg-subtle">{{ c.duration }}{{ c.duration_in_months ? ` · ${c.duration_in_months}mo` : "" }}</td>
            <td class="py-2 px-3 tabular-nums">{{ c.times_redeemed }}{{ c.max_redemptions ? ` / ${c.max_redemptions}` : "" }}</td>
            <td class="py-2 px-3" :style="c.valid ? { color: 'var(--signal-green)' } : { color: 'var(--signal-red)' }">{{ c.valid ? "valid" : "invalid" }}</td>
            <td class="py-2 px-3 text-right">
              <button
                type="button"
                class="text-[11px] text-fg-subtle hover:text-signal-red transition-colors"
                @click="openDelete(c)"
              >delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
