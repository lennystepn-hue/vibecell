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

const newCoupon = ref({
  code: "", name: "", percent_off: 20, amount_off_cents: 0,
  duration: "once" as "once" | "repeating" | "forever",
  duration_in_months: 1, max_redemptions: 100, use_amount: false,
});

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
  newCoupon.value = {
    code: "", name: "", percent_off: 20, amount_off_cents: 0,
    duration: "once", duration_in_months: 1, max_redemptions: 100, use_amount: false,
  };
  adminActions.open({
    kind: "create-coupon",
    url: "/api/v1/admin/coupons",
    body: () => {
      const c = newCoupon.value;
      return {
        code: c.code.trim(),
        name: c.name.trim() || null,
        percent_off: c.use_amount ? null : c.percent_off,
        amount_off_cents: c.use_amount ? c.amount_off_cents : null,
        duration: c.duration,
        duration_in_months: c.duration === "repeating" ? c.duration_in_months : null,
        max_redemptions: c.max_redemptions || null,
      };
    },
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

    <!-- Create form (always visible above the list) -->
    <section class="glass rounded-lg p-5 mb-6">
      <h3 class="mono-label text-fg-muted mb-3">// new coupon (configure here, click + new coupon to confirm with 2FA)</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <label class="block">
          <span class="mono-label">// code</span>
          <input v-model="newCoupon.code" type="text" maxlength="40" placeholder="LAUNCH69" class="mt-1 h-10 w-full px-3 rounded-md font-mono uppercase bg-bg-surface border border-border text-fg-primary" />
        </label>
        <label class="block">
          <span class="mono-label">// display name (optional)</span>
          <input v-model="newCoupon.name" type="text" maxlength="40" class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary" />
        </label>
        <label class="flex items-center gap-2 text-small text-fg-body sm:col-span-2">
          <input v-model="newCoupon.use_amount" type="checkbox" class="accent-signal-green" /> fixed-amount discount instead of percent
        </label>
        <label v-if="!newCoupon.use_amount" class="block">
          <span class="mono-label">// percent off</span>
          <input v-model.number="newCoupon.percent_off" type="number" min="1" max="100" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
        </label>
        <label v-else class="block">
          <span class="mono-label">// cents (eur)</span>
          <input v-model.number="newCoupon.amount_off_cents" type="number" min="50" max="100000" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
        </label>
        <label class="block">
          <span class="mono-label">// duration</span>
          <select v-model="newCoupon.duration" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary">
            <option value="once">once</option>
            <option value="repeating">repeating</option>
            <option value="forever">forever</option>
          </select>
        </label>
        <label v-if="newCoupon.duration === 'repeating'" class="block">
          <span class="mono-label">// months</span>
          <input v-model.number="newCoupon.duration_in_months" type="number" min="1" max="24" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
        </label>
        <label class="block sm:col-span-2">
          <span class="mono-label">// max redemptions (0 = unlimited)</span>
          <input v-model.number="newCoupon.max_redemptions" type="number" min="0" max="10000" class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary" />
        </label>
      </div>
    </section>

    <!-- Existing coupons -->
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
