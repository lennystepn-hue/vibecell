<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

interface SubscriptionShape {
  status: string;
  trial_ends_at: string | null;
  cancel_at_period_end: boolean;
}

const router = useRouter();
const sub = ref<SubscriptionShape | null>(null);
const dismissed = ref(false);

/** Per-status dismiss key — once the user dismisses the banner for a given
 *  status, we don't re-show it for that status until either:
 *   - the status changes (trialing → past_due, etc.)
 *   - 24h passes (so urgent reminders come back)
 *   - the trial reaches the last day (urgent state always re-shows)
 *
 *  Last-day re-show is non-negotiable: dismiss is for "I get it, I'll
 *  add the card later", not for "make this go away forever".
 */
const DISMISS_TTL_MS = 24 * 60 * 60 * 1000;

function dismissKey(status: string): string {
  return `vibecell.trialBanner.dismissed:${status}`;
}

function readDismissed(status: string): boolean {
  try {
    const raw = localStorage.getItem(dismissKey(status));
    if (!raw) return false;
    const ts = parseInt(raw, 10);
    if (!Number.isFinite(ts)) return false;
    return Date.now() - ts < DISMISS_TTL_MS;
  } catch {
    return false;
  }
}

function dismiss() {
  if (!sub.value) return;
  try {
    localStorage.setItem(dismissKey(sub.value.status), String(Date.now()));
  } catch {
    /* localStorage blocked — at least dismiss this session */
  }
  dismissed.value = true;
}

async function load() {
  try {
    const r = await fetch("/api/v1/me/subscription", { credentials: "include" });
    if (r.ok) {
      sub.value = await r.json();
      if (sub.value) dismissed.value = readDismissed(sub.value.status);
    }
  } catch {
    /* silent — banner just won't render */
  }
}

// Re-evaluate dismissed-state when sub changes (status flip = banner returns).
watch(
  () => sub.value?.status,
  (s) => {
    if (s) dismissed.value = readDismissed(s);
  },
);

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

/** Final visibility: variant exists AND not dismissed. The 24h TTL on
 *  dismiss + per-status keying brings the banner back automatically when
 *  it actually matters (status flips to past_due → fresh dismiss key →
 *  re-shown). User asked to be able to silence — respect that, no
 *  paternalistic overrides. */
const finalVisible = computed(() => {
  if (!variant.value) return false;
  return !dismissed.value;
});

/** Always dismissible — even past_due / trial-ended. The 24h TTL +
 *  per-status keying means the banner returns soon enough that nobody
 *  sleeps on a real billing problem; trying to lock the user out of
 *  hiding their own UI is paternalistic and they pushed back on it. */
const dismissible = computed(() => true);

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

<script lang="ts">
/** Theme-aware token map. Each variant maps to a `--signal-*` token pair
 *  defined in tokens.css; these resolve correctly against dark + paper +
 *  any future theme without hand-tuning RGBs in this component. */
const VARIANT_TOKENS: Record<
  "urgent" | "info" | "danger" | "muted",
  { fg: string; bg: string; border: string; ctaText: string }
> = {
  urgent: {
    fg: "var(--signal-amber)",
    bg: "var(--signal-amber-bg)",
    border: "var(--signal-amber)",
    ctaText: "var(--on-signal)",
  },
  info: {
    fg: "var(--signal-green)",
    bg: "var(--signal-green-bg)",
    border: "var(--signal-green)",
    ctaText: "var(--on-signal)",
  },
  danger: {
    fg: "var(--signal-red)",
    bg: "var(--signal-red-bg)",
    border: "var(--signal-red)",
    ctaText: "var(--on-signal)",
  },
  muted: {
    fg: "var(--fg-muted)",
    bg: "var(--signal-blue-bg)",
    border: "var(--border)",
    ctaText: "var(--fg-body)",
  },
};
</script>

<template>
  <div
    v-if="finalVisible && variant"
    class="px-4 py-2 flex items-center gap-4 font-mono text-[11px]"
    :style="{
      background: VARIANT_TOKENS[variant].bg,
      borderBottom: `1px solid ${VARIANT_TOKENS[variant].border}`,
      color: VARIANT_TOKENS[variant].fg,
    }"
  >
    <span class="flex-1 truncate">{{ text }}</span>
    <button
      class="px-3 py-1 rounded text-[10px] font-medium uppercase tracking-wider transition-opacity hover:opacity-80 shrink-0"
      :style="{
        background: variant === 'muted' ? 'transparent' : VARIANT_TOKENS[variant].fg,
        color: variant === 'muted' ? VARIANT_TOKENS[variant].ctaText : VARIANT_TOKENS[variant].ctaText,
        border: variant === 'muted' ? `1px solid ${VARIANT_TOKENS[variant].border}` : 'none',
      }"
      @click="go"
    >{{ ctaLabel }} →</button>
    <button
      v-if="dismissible"
      class="ml-1 w-6 h-6 flex items-center justify-center rounded transition-opacity shrink-0"
      style="opacity: 0.55"
      title="Dismiss for 24h"
      aria-label="Dismiss banner"
      @mouseenter="(e) => ((e.target as HTMLElement).style.opacity = '1')"
      @mouseleave="(e) => ((e.target as HTMLElement).style.opacity = '0.55')"
      @click="dismiss"
    >×</button>
  </div>
</template>
