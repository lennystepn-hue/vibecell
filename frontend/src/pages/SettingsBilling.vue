<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SettingsNav from "@/components/settings/SettingsNav.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

interface SubscriptionResponse {
  status: string;
  plan_slug: string;
  plan_name: string;
  monthly_price_eur_cents: number;
  trial_ends_at: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

const sub = ref<SubscriptionResponse | null>(null);
const loadingSub = ref(false);
const checkingOut = ref(false);
const openingPortal = ref(false);
const stripeNotConfigured = ref(false);

async function loadSubscription() {
  loadingSub.value = true;
  try {
    const r = await fetch("/api/v1/me/subscription", { credentials: "include" });
    if (r.ok) {
      sub.value = await r.json();
    } else if (r.status === 503) {
      stripeNotConfigured.value = true;
    } else if (r.status === 404) {
      // /me/subscription not yet implemented — fall back to feature-flag UI
      stripeNotConfigured.value = true;
    }
  } finally {
    loadingSub.value = false;
  }
}

async function startCheckout() {
  checkingOut.value = true;
  try {
    const r = await fetch("/api/v1/billing/checkout", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: "pro" }),
    });
    if (r.status === 503) {
      stripeNotConfigured.value = true;
      toast.push("Stripe is not configured on this deployment yet", "error");
      return;
    }
    if (!r.ok) {
      toast.push(`Couldn't start checkout (HTTP ${r.status})`, "error");
      return;
    }
    const { url } = await r.json();
    window.location.assign(url);
  } catch (e) {
    toast.push(`Network error: ${e instanceof Error ? e.message : String(e)}`, "error");
  } finally {
    checkingOut.value = false;
  }
}

async function openPortal() {
  openingPortal.value = true;
  try {
    const r = await fetch("/api/v1/billing/portal", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ return_url: "/settings/billing" }),
    });
    if (!r.ok) {
      toast.push(`Couldn't open portal (HTTP ${r.status})`, "error");
      return;
    }
    const { url } = await r.json();
    window.location.assign(url);
  } finally {
    openingPortal.value = false;
  }
}

const trialDaysLeft = computed(() => {
  if (!sub.value?.trial_ends_at) return null;
  const ms = new Date(sub.value.trial_ends_at).getTime() - Date.now();
  if (ms <= 0) return 0;
  return Math.ceil(ms / (24 * 60 * 60 * 1000));
});

const formattedPrice = computed(() => {
  if (!sub.value) return "";
  return `€${(sub.value.monthly_price_eur_cents / 100).toFixed(2)}/month`;
});

const statusLabel = computed(() => {
  if (!sub.value) return "";
  return {
    trialing: "Trial",
    active: "Active",
    past_due: "Payment failed",
    canceled: "Canceled",
    incomplete: "Incomplete",
    paused: "Paused",
    unpaid: "Unpaid",
  }[sub.value.status] ?? sub.value.status;
});

onMounted(loadSubscription);
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-[720px] mx-auto px-8 py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Billing</h1>

        <div v-if="loadingSub" class="text-fg-muted">Loading…</div>

        <div v-else-if="stripeNotConfigured">
          <SettingsSection
            title="Stripe not configured yet"
            subtitle="Billing endpoints return 503 until the operator wires Stripe credentials. This is fine for self-hosted deployments that don't sell to external users."
          >
            <PrimaryButton :disabled="checkingOut" :loading="checkingOut" @click="startCheckout">
              Try anyway (will fail with a 503 toast)
            </PrimaryButton>
          </SettingsSection>
        </div>

        <div v-else-if="sub">
          <SettingsSection
            title="Current plan"
            :subtitle="`${sub.plan_name} — ${formattedPrice}`"
          >
            <div class="space-y-3">
              <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                <span class="mono-label">status</span>
                <span class="font-mono text-body" :class="{
                  'text-signal-green': sub.status === 'active' || sub.status === 'trialing',
                  'text-signal-red': sub.status === 'past_due' || sub.status === 'unpaid',
                  'text-fg-muted': sub.status === 'canceled',
                }">{{ statusLabel }}</span>
              </div>
              <div v-if="sub.status === 'trialing' && trialDaysLeft !== null" class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                <span class="mono-label">trial ends</span>
                <span class="font-mono text-body text-fg-body">
                  in {{ trialDaysLeft }} {{ trialDaysLeft === 1 ? "day" : "days" }}
                </span>
              </div>
              <div v-if="sub.current_period_end" class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                <span class="mono-label">renews</span>
                <span class="font-mono text-small text-fg-muted">
                  {{ new Date(sub.current_period_end).toLocaleDateString() }}
                  <span v-if="sub.cancel_at_period_end" class="text-signal-red">
                    (will NOT renew)
                  </span>
                </span>
              </div>
            </div>
          </SettingsSection>

          <SettingsSection
            v-if="sub.status === 'trialing' || sub.status === 'past_due'"
            title="Add payment method"
            subtitle="Continue beyond trial / fix a failed payment via Stripe-hosted checkout."
          >
            <PrimaryButton :disabled="checkingOut" :loading="checkingOut" @click="startCheckout">
              {{ sub.status === "past_due" ? "Update payment method" : "Add card" }}
            </PrimaryButton>
          </SettingsSection>

          <SettingsSection
            v-if="sub.status === 'active' || sub.status === 'past_due'"
            title="Manage subscription"
            subtitle="Stripe-hosted portal — change card, view invoices, cancel."
          >
            <button
              type="button"
              class="h-10 px-4 rounded-md text-body transition-colors"
              :style="{ border: '1px solid var(--border)' }"
              :disabled="openingPortal"
              @click="openPortal"
            >
              {{ openingPortal ? "Opening…" : "Open Stripe Customer Portal" }}
            </button>
          </SettingsSection>
        </div>
      </div>
    </div>
  </div>
</template>
