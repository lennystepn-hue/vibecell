<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

interface SubscriptionShape {
  status: string;
  trial_ends_at: string | null;
  cancel_at_period_end: boolean;
}

const router = useRouter();
const sub = ref<SubscriptionShape | null>(null);

async function load() {
  try {
    const r = await fetch("/api/v1/me/subscription", { credentials: "include" });
    if (r.ok) sub.value = await r.json();
  } catch {
    /* silent — banner just won't render */
  }
}

const trialDaysLeft = computed(() => {
  if (!sub.value?.trial_ends_at) return null;
  const ms = new Date(sub.value.trial_ends_at).getTime() - Date.now();
  if (ms <= 0) return 0;
  return Math.ceil(ms / (24 * 60 * 60 * 1000));
});

/** Banner cases:
 *  - status=trialing AND trial ends in <= 3 days  → urgent yellow
 *  - status=trialing AND trial ends > 3 days       → soft mint
 *  - status=past_due                                → red "payment failed"
 *  - status=canceled                                → muted "canceled — re-subscribe"
 *  - else (active, paused, ...)                    → no banner
 */
const variant = computed<"urgent" | "info" | "danger" | "muted" | null>(() => {
  if (!sub.value) return null;
  if (sub.value.status === "trialing") {
    if (trialDaysLeft.value !== null && trialDaysLeft.value <= 3) return "urgent";
    return "info";
  }
  if (sub.value.status === "past_due" || sub.value.status === "unpaid") return "danger";
  if (sub.value.status === "canceled") return "muted";
  return null;
});

const text = computed(() => {
  if (!sub.value) return "";
  const days = trialDaysLeft.value;
  switch (sub.value.status) {
    case "trialing":
      if (days === null) return "Trial active — add a card any time.";
      if (days <= 0) return "Trial ended — add a card to keep using Pro features.";
      if (days === 1) return "Trial ends tomorrow — add a card to keep going.";
      return `Trial: ${days} days left`;
    case "past_due":
    case "unpaid":
      return "Payment failed — update your card to restore Pro access.";
    case "canceled":
      return "Subscription canceled — re-subscribe to use Pro features.";
    default:
      return "";
  }
});

const ctaLabel = computed(() => {
  if (!sub.value) return "";
  switch (sub.value.status) {
    case "trialing":
      return trialDaysLeft.value !== null && trialDaysLeft.value <= 0 ? "Add card" : "Add card";
    case "past_due":
    case "unpaid":
      return "Update payment";
    case "canceled":
      return "Re-subscribe";
    default:
      return "Open billing";
  }
});

function go() {
  router.push("/settings/billing");
}

onMounted(load);
</script>

<template>
  <div
    v-if="variant"
    class="px-4 py-2 flex items-center justify-between gap-4 font-mono"
    :style="{
      background:
        variant === 'urgent' ? 'rgba(255,200,80,0.08)' :
        variant === 'info' ? 'rgba(92,200,164,0.07)' :
        variant === 'danger' ? 'rgba(255,126,108,0.1)' :
        'rgba(138,180,255,0.06)',
      borderBottom: '1px solid ' + (
        variant === 'urgent' ? 'rgba(255,200,80,0.25)' :
        variant === 'info' ? 'rgba(92,200,164,0.18)' :
        variant === 'danger' ? 'rgba(255,126,108,0.3)' :
        'rgba(138,180,255,0.12)'
      ),
      fontSize: '11px',
    }"
  >
    <span :style="{
      color:
        variant === 'urgent' ? '#ffd66b' :
        variant === 'info' ? '#5cc8a4' :
        variant === 'danger' ? '#ff7e6c' :
        '#8ba1bd',
    }">
      {{ text }}
    </span>
    <button
      class="px-3 py-1 rounded text-[10px] font-medium uppercase tracking-wider transition-opacity hover:opacity-80"
      :style="{
        background:
          variant === 'urgent' ? '#ffd66b' :
          variant === 'info' ? '#5cc8a4' :
          variant === 'danger' ? '#ff7e6c' :
          'transparent',
        color:
          variant === 'muted' ? '#8ba1bd' : '#070b10',
        border: variant === 'muted' ? '1px solid rgba(138,180,255,0.2)' : 'none',
      }"
      @click="go"
    >{{ ctaLabel }} →</button>
  </div>
</template>
